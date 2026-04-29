"""Tests for retcon audit persistence contracts."""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.persistence.migrations import apply_migrations, current_schema_version
from sagasmith.persistence.repositories import TurnRecordRepository
from sagasmith.schemas.persistence import RetconAuditRecord, TurnRecord, VaultWriteAuditRecord


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
