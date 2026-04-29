"""Typed SQLite repositories for each trust-records table."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from sagasmith.schemas.mechanics import RollResult
from sagasmith.schemas.persistence import (
    AgentSkillLogRecord,
    CheckpointRef,
    CostLogRecord,
    SafetyEventRecord,
    StateDeltaRecord,
    TranscriptEntry,
    TurnRecord,
)
from sagasmith.schemas.provider import ProviderLogRecord


@dataclass(frozen=True)
class TranscriptRepository:
    conn: sqlite3.Connection

    def append(self, entry: TranscriptEntry) -> int:
        cursor = self.conn.execute(
            "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
            (entry.turn_id, entry.kind, entry.content, entry.sequence, entry.created_at),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def list_for_turn(self, turn_id: str) -> list[TranscriptEntry]:
        rows = self.conn.execute(
            "SELECT turn_id, kind, content, sequence, created_at FROM transcript_entries WHERE turn_id = ? ORDER BY sequence",
            (turn_id,),
        ).fetchall()
        return [
            TranscriptEntry(
                turn_id=row[0],
                kind=row[1],
                content=row[2],
                sequence=row[3],
                created_at=row[4],
            )
            for row in rows
        ]

    def list_recent(self, *, limit: int = 5) -> list[TranscriptEntry]:
        """Return recent transcript entries in chronological order."""
        rows = self.conn.execute(
            """
            SELECT turn_id, kind, content, sequence, created_at
              FROM transcript_entries
             ORDER BY id DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            TranscriptEntry(
                turn_id=row[0],
                kind=row[1],
                content=row[2],
                sequence=row[3],
                created_at=row[4],
            )
            for row in reversed(rows)
        ]


@dataclass(frozen=True)
class RollLogRepository:
    conn: sqlite3.Connection

    def append_from_roll(self, roll: RollResult, *, turn_id: str | None = None) -> str:
        self.conn.execute(
            "INSERT INTO roll_logs (roll_id, turn_id, seed, die, natural, modifier, total, dc, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                roll.roll_id,
                turn_id,
                roll.seed,
                roll.die,
                roll.natural,
                roll.modifier,
                roll.total,
                roll.dc,
                roll.timestamp,
            ),
        )
        return roll.roll_id

    def list_for_turn(self, turn_id: str) -> list[RollResult]:
        rows = self.conn.execute(
            "SELECT roll_id, seed, die, natural, modifier, total, dc, timestamp FROM roll_logs WHERE turn_id = ?",
            (turn_id,),
        ).fetchall()
        return [
            RollResult(
                roll_id=row[0],
                seed=row[1],
                die=row[2],
                natural=row[3],
                modifier=row[4],
                total=row[5],
                dc=row[6],
                timestamp=row[7],
            )
            for row in rows
        ]


@dataclass(frozen=True)
class ProviderLogRepository:
    conn: sqlite3.Connection

    def append(self, record: ProviderLogRecord) -> int:
        usage = record.usage
        cursor = self.conn.execute(
            """
            INSERT INTO provider_logs (
                request_id, provider, model, agent_name, turn_id, provider_response_id,
                failure_kind, retry_count, prompt_tokens, completion_tokens, total_tokens,
                cached_prompt_tokens, provider_cost_usd, cost_estimate_usd, latency_ms,
                safe_snippet, response_hash, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.request_id,
                record.provider,
                record.model,
                record.agent_name,
                record.turn_id,
                record.provider_response_id,
                record.failure_kind,
                record.retry_count,
                usage.prompt_tokens if usage else None,
                usage.completion_tokens if usage else None,
                usage.total_tokens if usage else None,
                usage.cached_prompt_tokens if usage else None,
                usage.provider_cost_usd if usage else None,
                record.cost_estimate_usd,
                record.latency_ms,
                record.safe_snippet,
                record.response_hash,
                record.timestamp,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def list_for_turn(self, turn_id: str) -> list[ProviderLogRecord]:
        rows = self.conn.execute(
            """
            SELECT request_id, provider, model, agent_name, turn_id, provider_response_id,
                   failure_kind, retry_count, prompt_tokens, completion_tokens, total_tokens,
                   cached_prompt_tokens, provider_cost_usd, cost_estimate_usd, latency_ms,
                   safe_snippet, response_hash, timestamp
            FROM provider_logs WHERE turn_id = ?
            """,
            (turn_id,),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row | tuple[Any, ...]) -> ProviderLogRecord:
        from sagasmith.schemas.provider import TokenUsage

        usage = None
        if row[8] is not None:
            usage = TokenUsage(
                prompt_tokens=row[8],
                completion_tokens=row[9] or 0,
                total_tokens=row[10] or 0,
                cached_prompt_tokens=row[11] or 0,
                provider_cost_usd=row[12],
            )
        return ProviderLogRecord(
            request_id=row[0],
            provider=row[1],
            model=row[2],
            agent_name=row[3],
            turn_id=row[4],
            provider_response_id=row[5],
            failure_kind=row[6],
            retry_count=row[7],
            usage=usage,
            cost_estimate_usd=row[13],
            latency_ms=row[14],
            safe_snippet=row[15],
            response_hash=row[16],
            timestamp=row[17],
        )


@dataclass(frozen=True)
class CostLogRepository:
    conn: sqlite3.Connection

    def append(self, record: CostLogRecord) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO cost_logs (
                turn_id, provider, model, agent_name, cost_usd, cost_is_approximate,
                tokens_prompt, tokens_completion, warnings_fired_json, spent_usd_after, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.turn_id,
                record.provider,
                record.model,
                record.agent_name,
                record.cost_usd,
                1 if record.cost_is_approximate else 0,
                record.tokens_prompt,
                record.tokens_completion,
                json.dumps(record.warnings_fired),
                record.spent_usd_after,
                record.timestamp,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def list_for_turn(self, turn_id: str) -> list[CostLogRecord]:
        rows = self.conn.execute(
            "SELECT turn_id, provider, model, agent_name, cost_usd, cost_is_approximate, tokens_prompt, tokens_completion, warnings_fired_json, spent_usd_after, timestamp FROM cost_logs WHERE turn_id = ?",
            (turn_id,),
        ).fetchall()
        return [
            CostLogRecord(
                turn_id=row[0],
                provider=row[1],
                model=row[2],
                agent_name=row[3],
                cost_usd=row[4],
                cost_is_approximate=bool(row[5]),
                tokens_prompt=row[6],
                tokens_completion=row[7],
                warnings_fired=json.loads(row[8]),
                spent_usd_after=row[9],
                timestamp=row[10],
            )
            for row in rows
        ]


@dataclass(frozen=True)
class StateDeltaRepository:
    conn: sqlite3.Connection

    def append(self, record: StateDeltaRecord) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO state_deltas (turn_id, delta_id, source, path, operation, value_json, reason, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.turn_id,
                record.delta_id,
                record.source,
                record.path,
                record.operation,
                record.value_json,
                record.reason,
                record.applied_at,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def list_for_turn(self, turn_id: str) -> list[StateDeltaRecord]:
        rows = self.conn.execute(
            "SELECT turn_id, delta_id, source, path, operation, value_json, reason, applied_at FROM state_deltas WHERE turn_id = ?",
            (turn_id,),
        ).fetchall()
        return [
            StateDeltaRecord(
                turn_id=row[0],
                delta_id=row[1],
                source=row[2],
                path=row[3],
                operation=row[4],
                value_json=row[5],
                reason=row[6],
                applied_at=row[7],
            )
            for row in rows
        ]


@dataclass(frozen=True)
class CheckpointRefRepository:
    conn: sqlite3.Connection

    def append(self, ref: CheckpointRef) -> str:
        self.conn.execute(
            "INSERT INTO checkpoint_refs (checkpoint_id, turn_id, kind, created_at) VALUES (?, ?, ?, ?)",
            (ref.checkpoint_id, ref.turn_id, ref.kind, ref.created_at),
        )
        return ref.checkpoint_id

    def list_for_turn(self, turn_id: str) -> list[CheckpointRef]:
        rows = self.conn.execute(
            "SELECT checkpoint_id, turn_id, kind, created_at FROM checkpoint_refs WHERE turn_id = ?",
            (turn_id,),
        ).fetchall()
        return [
            CheckpointRef(
                checkpoint_id=row[0],
                turn_id=row[1],
                kind=row[2],
                created_at=row[3],
            )
            for row in rows
        ]


@dataclass(frozen=True)
class TurnRecordRepository:
    conn: sqlite3.Connection

    def upsert(self, record: TurnRecord) -> str:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO turn_records (
                turn_id, campaign_id, session_id, status, started_at, completed_at,
                schema_version, sync_warning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.turn_id,
                record.campaign_id,
                record.session_id,
                record.status,
                record.started_at,
                record.completed_at,
                record.schema_version,
                record.sync_warning,
            ),
        )
        return record.turn_id

    def get(self, turn_id: str) -> TurnRecord | None:
        row = self.conn.execute(
            """
            SELECT turn_id, campaign_id, session_id, status, started_at, completed_at,
                   schema_version, sync_warning
              FROM turn_records WHERE turn_id = ?
            """,
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        return TurnRecord(
            turn_id=row[0],
            campaign_id=row[1],
            session_id=row[2],
            status=row[3],
            started_at=row[4],
            completed_at=row[5],
            schema_version=row[6],
            sync_warning=row[7],
        )


@dataclass(frozen=True)
class AgentSkillLogRepository:
    conn: sqlite3.Connection

    def append(self, record: AgentSkillLogRecord) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO agent_skill_log
                (turn_id, agent_name, skill_name, started_at, completed_at, outcome)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.turn_id,
                record.agent_name,
                record.skill_name,
                record.started_at,
                record.completed_at,
                record.outcome,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def list_for_turn(self, turn_id: str) -> list[AgentSkillLogRecord]:
        rows = self.conn.execute(
            """
            SELECT turn_id, agent_name, skill_name, started_at, completed_at, outcome
            FROM agent_skill_log
            WHERE turn_id = ?
            ORDER BY id
            """,
            (turn_id,),
        ).fetchall()
        return [
            AgentSkillLogRecord(
                turn_id=row[0],
                agent_name=row[1],
                skill_name=row[2],
                started_at=row[3],
                completed_at=row[4],
                outcome=row[5],
            )
            for row in rows
        ]

    def list_for_agent(self, agent_name: str, *, limit: int = 50) -> list[AgentSkillLogRecord]:
        rows = self.conn.execute(
            """
            SELECT turn_id, agent_name, skill_name, started_at, completed_at, outcome
            FROM agent_skill_log
            WHERE agent_name = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (agent_name, limit),
        ).fetchall()
        return [
            AgentSkillLogRecord(
                turn_id=row[0],
                agent_name=row[1],
                skill_name=row[2],
                started_at=row[3],
                completed_at=row[4],
                outcome=row[5],
            )
            for row in rows
        ]


@dataclass(frozen=True)
class SafetyEventRepository:
    conn: sqlite3.Connection

    def append(self, record: SafetyEventRecord) -> str:
        self.conn.execute(
            """
            INSERT INTO safety_events
              (event_id, campaign_id, turn_id, kind, policy_ref, action_taken, timestamp, visibility)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.event_id, record.campaign_id, record.turn_id,
                record.kind, record.policy_ref, record.action_taken,
                record.timestamp, record.visibility,
            ),
        )
        return record.event_id

    def list_for_campaign(self, campaign_id: str, *, limit: int = 20) -> list[SafetyEventRecord]:
        rows = self.conn.execute(
            """
            SELECT event_id, campaign_id, turn_id, kind, policy_ref, action_taken, timestamp, visibility
              FROM safety_events
             WHERE campaign_id = ?
             ORDER BY timestamp DESC
             LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()
        return [
            SafetyEventRecord(
                event_id=row[0], campaign_id=row[1], turn_id=row[2],
                kind=row[3], policy_ref=row[4], action_taken=row[5],
                timestamp=row[6], visibility=row[7],
            )
            for row in rows
        ]
