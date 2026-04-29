"""Provider-free integration coverage for checkpoint-based retcon execution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

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
from sagasmith.schemas.persistence import CheckpointRef, TranscriptEntry, TurnRecord, VaultWriteAuditRecord

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
    _seed_complete_turn(conn, "turn-1", minute=1, summary="The first canon event.", checkpoint_id="cp-1")
    _seed_complete_turn(conn, "turn-2", minute=2, summary="The second canon event.", checkpoint_id="cp-2")
    TurnRecordRepository(conn).upsert(_turn("turn-bad", status="needs_vault_repair", minute=3))

    candidates = RetconService(conn, campaign_id="cmp-retcon").list_candidates(limit=5)

    assert [candidate.turn_id for candidate in candidates] == ["turn-2", "turn-1"]
    assert candidates[0].summary == "The second canon event."
    assert candidates[0].completed_at == "2026-04-29T10:02:30Z"


def test_preview_returns_suffix_prior_checkpoint_impact_and_token() -> None:
    conn = _make_conn()
    _seed_complete_turn(conn, "turn-1", minute=1, summary="Safe prior canon.", checkpoint_id="cp-1")
    _seed_complete_turn(conn, "turn-2", minute=2, summary="Selected canon.", checkpoint_id="cp-2", vault_path="sessions/session-1.md")
    _seed_complete_turn(conn, "turn-3", minute=3, summary="Later canon.", checkpoint_id="cp-3", vault_path="npcs/npc-later.md")

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
    _seed_complete_turn(conn, "turn-1", minute=1, summary="No prior checkpoint.", checkpoint_id="cp-1")

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
class _RuntimeSpy:
    rewinded: list[str]

    def _rewind_to_checkpoint(self, checkpoint_id: str, *, clear_pending_narration: bool = False) -> None:
        self.rewinded.append(checkpoint_id)


@dataclass
class _VaultSpy:
    master_path: Path
    player_vault_root: Path
    synced: bool = False

    def sync(self) -> None:
        self.synced = True
