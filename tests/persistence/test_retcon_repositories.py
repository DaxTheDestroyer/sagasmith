"""Tests for retcon audit persistence contracts."""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.persistence.migrations import apply_migrations, current_schema_version
from sagasmith.persistence.repositories import (
    RetconAuditRepository,
    TranscriptRepository,
    TurnRecordRepository,
    VaultWriteAuditRepository,
)
from sagasmith.schemas.persistence import (
    RetconAuditRecord,
    TranscriptEntry,
    TurnRecord,
    VaultWriteAuditRecord,
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _turn(turn_id: str, *, status: str = "complete", completed_at: str = "2026-04-29T10:00:00Z") -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        campaign_id="campaign-1",
        session_id="session-1",
        status=status,  # type: ignore[arg-type]
        started_at="2026-04-29T09:59:00Z",
        completed_at=completed_at,
        schema_version=1,
    )


def test_retcon_migration_reaches_schema_version_8() -> None:
    conn = _make_conn()

    applied = apply_migrations(conn)

    assert applied == [1, 2, 3, 4, 5, 6, 7, 8]
    assert current_schema_version(conn) == 8
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"retcon_audit", "vault_write_audit"} <= tables


def test_turn_record_retconned_status_round_trips_through_repository() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    repo = TurnRecordRepository(conn)
    original = _turn("turn-retconned", status="retconned")

    repo.upsert(original)

    assert repo.get("turn-retconned") == original


def test_retcon_audit_record_requires_rollback_metadata() -> None:
    record = RetconAuditRecord(
        retcon_id="retcon-1",
        campaign_id="campaign-1",
        selected_turn_id="turn-2",
        affected_turn_ids=["turn-2", "turn-3"],
        prior_checkpoint_id="checkpoint-1",
        confirmation_token="RETCON turn-2",
        reason="Player corrected accidental canon.",
        created_at="2026-04-29T10:05:00Z",
    )

    assert record.selected_turn_id == "turn-2"
    assert record.affected_turn_ids == ["turn-2", "turn-3"]

    with pytest.raises(ValueError):
        RetconAuditRecord(
            retcon_id="retcon-2",
            campaign_id="campaign-1",
            selected_turn_id="turn-2",
            affected_turn_ids=[],
            prior_checkpoint_id="checkpoint-1",
            confirmation_token="RETCON turn-2",
            reason="Player corrected accidental canon.",
            created_at="2026-04-29T10:05:00Z",
        )


def test_vault_write_audit_record_captures_turn_path_operation_and_time() -> None:
    record = VaultWriteAuditRecord(
        turn_id="turn-1",
        vault_path="sessions/session-1.md",
        operation="write_page",
        recorded_at="2026-04-29T10:06:00Z",
    )

    assert record.turn_id == "turn-1"
    assert record.vault_path == "sessions/session-1.md"
    assert record.operation == "write_page"
    assert record.recorded_at == "2026-04-29T10:06:00Z"


def test_recent_completed_returns_only_complete_turns_newest_first() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    repo = TurnRecordRepository(conn)
    repo.upsert(_turn("turn-old", completed_at="2026-04-29T10:00:00Z"))
    repo.upsert(_turn("turn-retconned", status="retconned", completed_at="2026-04-29T10:01:00Z"))
    repo.upsert(_turn("turn-new", completed_at="2026-04-29T10:02:00Z"))

    turns = repo.list_recent_completed("campaign-1", limit=5)

    assert [turn.turn_id for turn in turns] == ["turn-new", "turn-old"]


def test_affected_suffix_includes_selected_and_later_completed_turns_only() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    repo = TurnRecordRepository(conn)
    repo.upsert(_turn("turn-1", completed_at="2026-04-29T10:00:00Z"))
    repo.upsert(_turn("turn-2", completed_at="2026-04-29T10:01:00Z"))
    repo.upsert(_turn("turn-3", status="retconned", completed_at="2026-04-29T10:02:00Z"))
    repo.upsert(_turn("turn-4", completed_at="2026-04-29T10:03:00Z"))

    suffix = repo.list_affected_suffix("campaign-1", "turn-2")

    assert [turn.turn_id for turn in suffix] == ["turn-2", "turn-4"]


def test_mark_retconned_preserves_rows_while_changing_status() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    repo = TurnRecordRepository(conn)
    repo.upsert(_turn("turn-1"))
    repo.upsert(_turn("turn-2"))

    repo.mark_retconned(["turn-1", "turn-2"])

    assert repo.get("turn-1") is not None
    assert repo.get("turn-1").status == "retconned"  # type: ignore[union-attr]
    assert repo.get("turn-2").status == "retconned"  # type: ignore[union-attr]


def test_canonical_transcript_excludes_retconned_turns_by_default() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    turns = TurnRecordRepository(conn)
    transcripts = TranscriptRepository(conn)
    turns.upsert(_turn("turn-1", completed_at="2026-04-29T10:00:00Z"))
    turns.upsert(_turn("turn-2", status="retconned", completed_at="2026-04-29T10:01:00Z"))
    for turn_id in ["turn-1", "turn-2"]:
        transcripts.append(
            TranscriptEntry(
                turn_id=turn_id,
                kind="narration_final",
                content=f"canon from {turn_id}",
                sequence=0,
                created_at="2026-04-29T10:02:00Z",
            )
        )

    canonical = transcripts.list_canonical_for_campaign("campaign-1", limit=8)
    debug = transcripts.list_canonical_for_campaign("campaign-1", limit=8, include_retconned=True)

    assert [entry.turn_id for entry in canonical] == ["turn-1"]
    assert [entry.turn_id for entry in debug] == ["turn-1", "turn-2"]


def test_retcon_and_vault_audit_repositories_round_trip() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    retcons = RetconAuditRepository(conn)
    vault_writes = VaultWriteAuditRepository(conn)
    retcon = RetconAuditRecord(
        retcon_id="retcon-1",
        campaign_id="campaign-1",
        selected_turn_id="turn-2",
        affected_turn_ids=["turn-2", "turn-3"],
        prior_checkpoint_id="checkpoint-1",
        confirmation_token="RETCON turn-2",
        reason="Player corrected accidental canon.",
        created_at="2026-04-29T10:05:00Z",
    )
    vault_write = VaultWriteAuditRecord(
        turn_id="turn-2",
        vault_path="sessions/session-1.md",
        operation="write_page",
        recorded_at="2026-04-29T10:06:00Z",
    )

    retcons.append(retcon)
    vault_writes.append(vault_write)

    assert retcons.get("retcon-1") == retcon
    assert vault_writes.list_for_turn("turn-2") == [vault_write]
    assert vault_writes.list_for_turns(["turn-2", "turn-3"]) == [vault_write]
