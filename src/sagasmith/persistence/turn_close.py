"""Transactional turn-close helper enforcing PERSISTENCE_SPEC §4."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from sagasmith.evals.redaction import RedactionCanary
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

from .repositories import (
    CheckpointRefRepository,
    CostLogRepository,
    ProviderLogRepository,
    RollLogRepository,
    StateDeltaRepository,
    TranscriptRepository,
    TurnRecordRepository,
)


@dataclass(frozen=True)
class TurnCloseBundle:
    """All data to atomically write during turn close."""

    turn_record: TurnRecord
    transcript_entries: list[TranscriptEntry]
    roll_results: list[tuple[RollResult, str | None]]
    provider_logs: list[ProviderLogRecord]
    state_deltas: list[StateDeltaRecord]
    cost_logs: list[CostLogRecord]
    checkpoint_refs: list[CheckpointRef]


def _assert_no_secret_shaped_payloads(bundle: TurnCloseBundle) -> None:
    canary = RedactionCanary()
    scan_targets: list[tuple[str, str]] = []

    for index, entry in enumerate(bundle.transcript_entries):
        scan_targets.append((f"transcript_entries[{index}]", entry.model_dump_json()))
    for index, (roll, _turn_id) in enumerate(bundle.roll_results):
        scan_targets.append((f"roll_results[{index}]", roll.model_dump_json()))
    for index, log in enumerate(bundle.provider_logs):
        scan_targets.append((f"provider_logs[{index}]", log.model_dump_json()))
    for index, delta in enumerate(bundle.state_deltas):
        scan_targets.append((f"state_deltas[{index}]", delta.model_dump_json()))
    for index, cost in enumerate(bundle.cost_logs):
        scan_targets.append((f"cost_logs[{index}]", cost.model_dump_json()))
    for index, ref in enumerate(bundle.checkpoint_refs):
        scan_targets.append((f"checkpoint_refs[{index}]", ref.model_dump_json()))

    for location, text in scan_targets:
        hits = canary.scan(text)
        if hits:
            raise TrustServiceError(
                f"turn-close redaction sweep failed: location={location} label={hits[0].label}"
            )


def close_turn(conn: sqlite3.Connection, bundle: TurnCloseBundle) -> TurnRecord:
    """Apply PERSISTENCE_SPEC §4 steps 1-7 atomically. Mark turn complete only on commit.

    Steps:
    1. BEGIN TRANSACTION
    2. Append transcript entries
    3. Append roll logs
    4. Append provider logs
    5. Append state deltas
    6. Append cost logs
    7. Append checkpoint refs
    8. Upsert turn record with status='complete'
    9. COMMIT
    """
    transcript_repo = TranscriptRepository(conn)
    roll_repo = RollLogRepository(conn)
    provider_repo = ProviderLogRepository(conn)
    delta_repo = StateDeltaRepository(conn)
    cost_repo = CostLogRepository(conn)
    checkpoint_repo = CheckpointRefRepository(conn)
    turn_repo = TurnRecordRepository(conn)

    try:
        _assert_no_secret_shaped_payloads(bundle)

        for entry in bundle.transcript_entries:
            transcript_repo.append(entry)

        for roll, turn_id_override in bundle.roll_results:
            roll_repo.append_from_roll(roll, turn_id=turn_id_override)

        for log in bundle.provider_logs:
            provider_repo.append(log)

        for delta in bundle.state_deltas:
            delta_repo.append(delta)

        for cost in bundle.cost_logs:
            cost_repo.append(cost)

        for ref in bundle.checkpoint_refs:
            checkpoint_repo.append(ref)

        now = datetime.now(UTC).isoformat()
        completed_record = TurnRecord(
            turn_id=bundle.turn_record.turn_id,
            campaign_id=bundle.turn_record.campaign_id,
            session_id=bundle.turn_record.session_id,
            status="complete",
            started_at=bundle.turn_record.started_at,
            completed_at=now,
            schema_version=bundle.turn_record.schema_version,
        )
        turn_repo.upsert(completed_record)

        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise TrustServiceError(f"turn-close failed: {exc}") from exc

    return completed_record
