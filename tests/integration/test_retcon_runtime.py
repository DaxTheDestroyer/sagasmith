"""Provider-free integration coverage for checkpoint-based retcon execution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import assemble_memory_packet
from sagasmith.graph.runtime import GraphRuntime
from sagasmith.memory.fts5 import FTS5Index
from sagasmith.memory.graph import get_vault_graph, reset_vault_graph_cache
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    CheckpointRefRepository,
    RetconAuditRepository,
    RollLogRepository,
    TranscriptRepository,
    TurnRecordRepository,
    VaultWriteAuditRepository,
)
from sagasmith.persistence.retcon import RetconBlockedError, RetconService
from sagasmith.schemas.mechanics import RollResult
from sagasmith.schemas.persistence import (
    CheckpointRef,
    TranscriptEntry,
    TurnRecord,
    VaultWriteAuditRecord,
)

pytestmark = pytest.mark.integration


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp-retcon", "Retcon", "retcon", "2026-04-29T10:00:00Z", "0.0.1", 1),
    )
    return conn


def _turn(turn_id: str, *, status: str = "complete", minute: int = 1) -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        campaign_id="cmp-retcon",
        session_id="session-1",
        status=status,  # type: ignore[arg-type]
        started_at=f"2026-04-29T10:{minute:02d}:00Z",
        completed_at=f"2026-04-29T10:{minute:02d}:30Z",
        schema_version=1,
    )


def _seed_complete_turn(
    conn: sqlite3.Connection,
    turn_id: str,
    *,
    minute: int,
    summary: str,
    checkpoint_id: str | None = None,
    vault_path: str | None = None,
) -> None:
    TurnRecordRepository(conn).upsert(_turn(turn_id, minute=minute))
    TranscriptRepository(conn).append(
        TranscriptEntry(
            turn_id=turn_id,
            kind="player_input",
            content=f"input for {turn_id}",
            sequence=0,
            created_at=f"2026-04-29T10:{minute:02d}:01Z",
        )
    )
    TranscriptRepository(conn).append(
        TranscriptEntry(
            turn_id=turn_id,
            kind="narration_final",
            content=summary,
            sequence=1,
            created_at=f"2026-04-29T10:{minute:02d}:20Z",
        )
    )
    RollLogRepository(conn).append_from_roll(
        RollResult(
            roll_id=f"roll-{turn_id}",
            seed=f"seed-{turn_id}",
            die="d20",
            natural=12,
            modifier=3,
            total=15,
            dc=14,
            timestamp=f"2026-04-29T10:{minute:02d}:10Z",
        ),
        turn_id=turn_id,
    )
    if checkpoint_id is not None:
        CheckpointRefRepository(conn).append(
            CheckpointRef(
                checkpoint_id=checkpoint_id,
                turn_id=turn_id,
                kind="final",
                created_at=f"2026-04-29T10:{minute:02d}:29Z",
            )
        )
    if vault_path is not None:
        VaultWriteAuditRepository(conn).append(
            VaultWriteAuditRecord(
                turn_id=turn_id,
                vault_path=vault_path,
                operation="write_page",
                recorded_at=f"2026-04-29T10:{minute:02d}:31Z",
            )
        )
    conn.commit()


def test_list_candidates_returns_recent_completed_turn_summaries() -> None:
    conn = _make_conn()
    _seed_complete_turn(
        conn, "turn-1", minute=1, summary="The first canon event.", checkpoint_id="cp-1"
    )
    _seed_complete_turn(
        conn, "turn-2", minute=2, summary="The second canon event.", checkpoint_id="cp-2"
    )
    TurnRecordRepository(conn).upsert(_turn("turn-bad", status="needs_vault_repair", minute=3))

    candidates = RetconService(conn, campaign_id="cmp-retcon").list_candidates(limit=5)

    assert [candidate.turn_id for candidate in candidates] == ["turn-2", "turn-1"]
    assert candidates[0].summary == "The second canon event."
    assert candidates[0].completed_at == "2026-04-29T10:02:30Z"


def test_preview_returns_suffix_prior_checkpoint_impact_and_token() -> None:
    conn = _make_conn()
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(
        conn,
        "turn-2",
        minute=2,
        summary="Selected canon.",
        checkpoint_id="cp-2",
        vault_path="sessions/session-1.md",
    )
    _seed_complete_turn(
        conn,
        "turn-3",
        minute=3,
        summary="Later canon.",
        checkpoint_id="cp-3",
        vault_path="npcs/npc-later.md",
    )

    preview = RetconService(conn, campaign_id="cmp-retcon").preview("turn-2")

    assert preview.selected_turn_id == "turn-2"
    assert preview.affected_turn_ids == ["turn-2", "turn-3"]
    assert preview.prior_checkpoint_id == "cp-1"
    assert preview.transcript_count == 4
    assert preview.roll_count == 2
    assert preview.vault_paths == ["sessions/session-1.md", "npcs/npc-later.md"]
    assert preview.confirmation_token == "RETCON turn-2"
    assert "state rewind" in preview.effects
    assert "affected transcript/mechanics/vault/memory outputs" in preview.effects
    assert "audit retention" in preview.effects
    assert "canonical exclusion after success" in preview.effects


def test_preview_blocks_when_no_prior_final_checkpoint_exists() -> None:
    conn = _make_conn()
    _seed_complete_turn(
        conn, "turn-1", minute=1, summary="No prior checkpoint.", checkpoint_id="cp-1"
    )

    with pytest.raises(RetconBlockedError) as exc:
        RetconService(conn, campaign_id="cmp-retcon").preview("turn-1")

    assert "repair" in exc.value.repair_guidance.lower()


def test_preview_blocks_when_selected_turn_is_not_complete() -> None:
    conn = _make_conn()
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Prior canon.", checkpoint_id="cp-1")
    TurnRecordRepository(conn).upsert(_turn("turn-2", status="needs_vault_repair", minute=2))
    conn.commit()

    with pytest.raises(RetconBlockedError) as exc:
        RetconService(conn, campaign_id="cmp-retcon").preview("turn-2")

    assert "complete" in str(exc.value)


@dataclass
class _VaultSpy:
    master_path: Path
    player_vault_root: Path
    synced: bool = False
    rebuild_calls: int = 0

    def sync(self) -> None:
        self.synced = True

    def rebuild_indices(self, conn: object | None = None) -> dict[str, int]:
        self.rebuild_calls += 1
        return {
            "graph_pages": 0,
            "fts5_pages": FTS5Index(conn).rebuild_all(self.master_path)
            if isinstance(conn, sqlite3.Connection)
            else 0,
        }


def _make_runtime(conn: sqlite3.Connection, vault_service: _VaultSpy) -> GraphRuntime:
    runtime = GraphRuntime(
        graph=SimpleNamespace(),
        db_conn=conn,
        campaign_id="cmp-retcon",
        bootstrap=SimpleNamespace(services=SimpleNamespace(vault_service=vault_service)),
    )

    def record_rewind(checkpoint_id: str) -> int:
        return vault_service.player_vault_root.joinpath("rewound.txt").write_text(
            checkpoint_id,
            encoding="utf-8",
        )

    setattr(
        runtime,
        "_rewind_to_checkpoint",
        record_rewind,
    )
    return runtime


def test_confirm_with_wrong_token_blocks_and_makes_no_status_changes() -> None:
    conn = _make_conn()
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(conn, "turn-2", minute=2, summary="Selected canon.", checkpoint_id="cp-2")

    with pytest.raises(RetconBlockedError):
        RetconService(conn, campaign_id="cmp-retcon").confirm("turn-2", "RETCON wrong")

    assert TurnRecordRepository(conn).get("turn-2").status == "complete"  # type: ignore[union-attr]
    assert conn.execute("SELECT COUNT(*) FROM retcon_audit").fetchone()[0] == 0


def test_runtime_confirm_retcon_rewinds_rebuilds_syncs_and_audits(tmp_path: Path) -> None:
    conn = _make_conn()
    master = tmp_path / "master"
    master.mkdir()
    (master / "canon.md").write_text(
        "---\nid: lore_canon\ntype: lore\nname: Canon\nvisibility: player_known\n---\n\nremaining canon",
        encoding="utf-8",
    )
    player = tmp_path / "player"
    player.mkdir()
    vault = _VaultSpy(master_path=master, player_vault_root=player)
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(
        conn,
        "turn-2",
        minute=2,
        summary="Selected removed canon.",
        checkpoint_id="cp-2",
        vault_path="canon.md",
    )
    _seed_complete_turn(
        conn, "turn-3", minute=3, summary="Later removed canon.", checkpoint_id="cp-3"
    )
    runtime = _make_runtime(conn, vault)

    result = runtime.confirm_retcon("turn-2", "RETCON turn-2")

    assert result.message.startswith("Retcon complete")
    assert player.joinpath("rewound.txt").read_text(encoding="utf-8") == "cp-1"
    assert vault.rebuild_calls == 1
    assert vault.synced is True
    assert TurnRecordRepository(conn).get("turn-2").status == "retconned"  # type: ignore[union-attr]
    assert TurnRecordRepository(conn).get("turn-3").status == "retconned"  # type: ignore[union-attr]
    assert RetconAuditRepository(conn).get(result.audit_id) is not None
    assert FTS5Index(conn).query("remaining")


def test_retconned_transcript_content_absent_from_canonical_context_and_memory_packet() -> None:
    conn = _make_conn()
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(
        conn, "turn-2", minute=2, summary="Forbidden removed canon detail.", checkpoint_id="cp-2"
    )
    RetconService(conn, campaign_id="cmp-retcon").confirm("turn-2", "RETCON turn-2")

    canonical = TranscriptRepository(conn).list_canonical_for_campaign("cmp-retcon", limit=8)
    packet = assemble_memory_packet(
        {"campaign_id": "cmp-retcon", "turn_id": "new", "session_state": {}}, conn=conn
    )

    assert all("Forbidden removed canon detail" not in entry.content for entry in canonical)
    assert all("Forbidden removed canon detail" not in turn for turn in packet.recent_turns)


def test_runtime_confirm_retcon_returns_without_session_exit(tmp_path: Path) -> None:
    conn = _make_conn()
    master = tmp_path / "master"
    master.mkdir()
    player = tmp_path / "player"
    player.mkdir()
    vault = _VaultSpy(master_path=master, player_vault_root=player)
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(conn, "turn-2", minute=2, summary="Selected canon.", checkpoint_id="cp-2")

    result = _make_runtime(conn, vault).confirm_retcon("turn-2", "RETCON turn-2")

    assert result.selected_turn_id == "turn-2"
    assert "excluded from canon" in result.message
    assert not result.message.lower().startswith("exit")
    reset_vault_graph_cache()
    assert get_vault_graph().get_all_node_ids() == []
