"""Tests for typed repositories."""

from __future__ import annotations

from pathlib import Path

from sagasmith.persistence.db import campaign_db
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    CheckpointRefRepository,
    CostLogRepository,
    ProviderLogRepository,
    RollLogRepository,
    StateDeltaRepository,
    TranscriptRepository,
    TurnRecordRepository,
)
from sagasmith.schemas.mechanics import RollResult
from sagasmith.schemas.persistence import (
    CheckpointRef,
    CostLogRecord,
    StateDeltaRecord,
    TranscriptEntry,
    TurnRecord,
)
from sagasmith.schemas.provider import ProviderLogRecord


def _db(tmp_path: Path) -> Path:
    return tmp_path / "repo_test.db"


def test_repository_round_trip_for_each_table(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        turn_id = "turn-001"
        tr = TurnRecordRepository(conn)
        tr.upsert(
            TurnRecord(
                turn_id=turn_id,
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:01:00Z",
                schema_version=1,
            )
        )

        te = TranscriptRepository(conn)
        te.append(
            TranscriptEntry(
                turn_id=turn_id,
                kind="player_input",
                content="hello",
                sequence=0,
                created_at="2026-04-26T12:00:00Z",
            )
        )

        rl = RollLogRepository(conn)
        roll = RollResult(
            roll_id="roll_1",
            seed="s",
            die="d20",
            natural=15,
            modifier=3,
            total=18,
            dc=15,
            timestamp="2026-04-26T12:00:00Z",
        )
        rl.append_from_roll(roll, turn_id=turn_id)

        pl = ProviderLogRepository(conn)
        pl.append(
            ProviderLogRecord(
                request_id="req-1",
                provider="fake",
                model="m",
                agent_name="a",
                turn_id=turn_id,
                failure_kind="none",
                retry_count=0,
                latency_ms=10,
                response_hash="abc123",
                timestamp="2026-04-26T12:00:00Z",
            )
        )

        sd = StateDeltaRepository(conn)
        sd.append(
            StateDeltaRecord(
                turn_id=turn_id,
                delta_id="d1",
                source="rules",
                path="hp",
                operation="increment",
                value_json="-3",
                reason="damage",
                applied_at="2026-04-26T12:00:00Z",
            )
        )

        cl = CostLogRepository(conn)
        cl.append(
            CostLogRecord(
                turn_id=turn_id,
                provider="fake",
                model="m",
                agent_name="a",
                cost_usd=0.01,
                cost_is_approximate=True,
                tokens_prompt=10,
                tokens_completion=5,
                warnings_fired=[],
                spent_usd_after=0.01,
                timestamp="2026-04-26T12:00:00Z",
            )
        )

        cp = CheckpointRefRepository(conn)
        cp.append(
            CheckpointRef(
                checkpoint_id="cp1",
                turn_id=turn_id,
                kind="final",
                created_at="2026-04-26T12:00:00Z",
            )
        )

        conn.commit()

        assert len(te.list_for_turn(turn_id)) == 1
        assert len(rl.list_for_turn(turn_id)) == 1
        assert len(pl.list_for_turn(turn_id)) == 1
        assert len(sd.list_for_turn(turn_id)) == 1
        assert len(cl.list_for_turn(turn_id)) == 1
        assert len(cp.list_for_turn(turn_id)) == 1
        assert tr.get(turn_id) is not None
