"""Tests for close_turn transactional semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.persistence.db import campaign_db
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import TurnRecordRepository
from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
from sagasmith.schemas.mechanics import RollResult
from sagasmith.schemas.persistence import (
    CheckpointRef,
    CostLogRecord,
    StateDeltaRecord,
    TranscriptEntry,
    TurnRecord,
)
from sagasmith.schemas.provider import ProviderLogRecord
from sagasmith.services.errors import TrustServiceError


def _db(tmp_path: Path) -> Path:
    return tmp_path / "turn_test.db"


def test_close_turn_commits_all_records_in_order(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[
                TranscriptEntry(
                    turn_id="t1",
                    kind="player_input",
                    content="hello",
                    sequence=0,
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
            roll_results=[
                (
                    RollResult(
                        roll_id="r1",
                        seed="s",
                        die="d20",
                        natural=10,
                        modifier=0,
                        total=10,
                        dc=None,
                        timestamp="2026-04-26T12:00:00Z",
                    ),
                    "t1",
                )
            ],
            provider_logs=[
                ProviderLogRecord(
                    request_id="req1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    turn_id="t1",
                    failure_kind="none",
                    retry_count=0,
                    latency_ms=0,
                    response_hash="abc",
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            state_deltas=[
                StateDeltaRecord(
                    turn_id="t1",
                    delta_id="d1",
                    source="rules",
                    path="hp",
                    operation="set",
                    value_json="10",
                    reason="init",
                    applied_at="2026-04-26T12:00:00Z",
                )
            ],
            cost_logs=[
                CostLogRecord(
                    turn_id="t1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    cost_usd=0.0,
                    cost_is_approximate=True,
                    tokens_prompt=0,
                    tokens_completion=0,
                    warnings_fired=[],
                    spent_usd_after=0.0,
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            checkpoint_refs=[
                CheckpointRef(
                    checkpoint_id="cp1",
                    turn_id="t1",
                    kind="final",
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
        )

        result = close_turn(conn, bundle)
        assert result.status == "complete"

        tr = TurnRecordRepository(conn)
        turn = tr.get("t1")
        assert turn is not None
        assert turn.status == "complete"

        # Verify transcript sequence order
        from sagasmith.persistence.repositories import TranscriptRepository

        entries = TranscriptRepository(conn).list_for_turn("t1")
        assert len(entries) == 1
        assert entries[0].sequence == 0


def test_close_turn_rollback_on_provider_log_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        from sagasmith.persistence.repositories import ProviderLogRepository

        def _failing_append(self: ProviderLogRecord, record: ProviderLogRecord) -> int:
            raise RuntimeError("injected provider log failure")

        monkeypatch.setattr(ProviderLogRepository, "append", _failing_append)

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[
                ProviderLogRecord(
                    request_id="req1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    turn_id="t1",
                    failure_kind="none",
                    retry_count=0,
                    latency_ms=0,
                    response_hash="abc",
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
        )

        with pytest.raises(TrustServiceError):
            close_turn(conn, bundle)

        tr = TurnRecordRepository(conn)
        assert tr.get("t1") is None


def test_close_turn_is_atomic_on_checkpoint_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        from sagasmith.persistence.repositories import CheckpointRefRepository

        def _failing_append(self: CheckpointRefRepository, ref: CheckpointRef) -> str:
            raise RuntimeError("injected checkpoint failure")

        monkeypatch.setattr(CheckpointRefRepository, "append", _failing_append)

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[],
            state_deltas=[
                StateDeltaRecord(
                    turn_id="t1",
                    delta_id="d1",
                    source="rules",
                    path="hp",
                    operation="set",
                    value_json="10",
                    reason="init",
                    applied_at="2026-04-26T12:00:00Z",
                )
            ],
            cost_logs=[],
            checkpoint_refs=[
                CheckpointRef(
                    checkpoint_id="cp1",
                    turn_id="t1",
                    kind="final",
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
        )

        with pytest.raises(TrustServiceError):
            close_turn(conn, bundle)

        from sagasmith.persistence.repositories import StateDeltaRepository

        sd = StateDeltaRepository(conn)
        assert sd.list_for_turn("t1") == []


def test_turn_not_marked_complete_when_transaction_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        from sagasmith.persistence.repositories import ProviderLogRepository

        def _failing_append(self: ProviderLogRepository, record: ProviderLogRecord) -> int:
            raise RuntimeError("injected failure for turn completeness test")

        monkeypatch.setattr(ProviderLogRepository, "append", _failing_append)

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[
                ProviderLogRecord(
                    request_id="req1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    turn_id="t1",
                    failure_kind="none",
                    retry_count=0,
                    latency_ms=0,
                    response_hash="abc",
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
        )

        with pytest.raises(TrustServiceError):
            close_turn(conn, bundle)

        tr = TurnRecordRepository(conn)
        assert tr.get("t1") is None


@pytest.mark.smoke
def test_close_turn_rejects_secret_shaped_payload_before_writes(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[
                TranscriptEntry(
                    turn_id="t1",
                    kind="player_input",
                    content="Authorization: Bearer abcdefghijklmnop",
                    sequence=0,
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
            roll_results=[],
            provider_logs=[],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
        )

        with pytest.raises(TrustServiceError, match="redaction sweep failed"):
            close_turn(conn, bundle)

        assert conn.execute("SELECT COUNT(*) FROM transcript_entries").fetchone()[0] == 0
        assert TurnRecordRepository(conn).get("t1") is None


def test_redaction_over_all_tables_clean(tmp_path: Path) -> None:
    from sagasmith.evals.redaction import RedactionCanary

    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        # Well-formed bundle with safe prose
        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[
                TranscriptEntry(
                    turn_id="t1",
                    kind="narration_final",
                    content="The hero opened the door.",
                    sequence=0,
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
            roll_results=[
                (
                    RollResult(
                        roll_id="r1",
                        seed="s",
                        die="d20",
                        natural=15,
                        modifier=0,
                        total=15,
                        dc=10,
                        timestamp="2026-04-26T12:00:00Z",
                    ),
                    "t1",
                )
            ],
            provider_logs=[
                ProviderLogRecord(
                    request_id="req1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    turn_id="t1",
                    failure_kind="none",
                    retry_count=0,
                    latency_ms=0,
                    safe_snippet="safe snippet",
                    response_hash="abc",
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            state_deltas=[
                StateDeltaRecord(
                    turn_id="t1",
                    delta_id="d1",
                    source="rules",
                    path="hp",
                    operation="set",
                    value_json="10",
                    reason="init",
                    applied_at="2026-04-26T12:00:00Z",
                )
            ],
            cost_logs=[
                CostLogRecord(
                    turn_id="t1",
                    provider="fake",
                    model="m",
                    agent_name="a",
                    cost_usd=0.0,
                    cost_is_approximate=True,
                    tokens_prompt=0,
                    tokens_completion=0,
                    warnings_fired=[],
                    spent_usd_after=0.0,
                    timestamp="2026-04-26T12:00:00Z",
                )
            ],
            checkpoint_refs=[
                CheckpointRef(
                    checkpoint_id="cp1",
                    turn_id="t1",
                    kind="final",
                    created_at="2026-04-26T12:00:00Z",
                )
            ],
        )

        close_turn(conn, bundle)

        tables = [
            "turn_records",
            "transcript_entries",
            "roll_logs",
            "provider_logs",
            "cost_logs",
            "state_deltas",
            "checkpoint_refs",
        ]
        blob = ""
        for table in tables:
            rows = conn.execute(f"SELECT * FROM {table} WHERE turn_id = 't1'").fetchall()
            blob += "\n".join(str(row) for row in rows)

        assert RedactionCanary().scan(blob) == []
