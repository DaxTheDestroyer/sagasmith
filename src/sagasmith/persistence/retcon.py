"""Checkpoint-based retcon preview and execution service."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sagasmith.persistence.repositories import (
    RetconAuditRepository,
    TranscriptRepository,
    TurnRecordRepository,
    VaultWriteAuditRepository,
)
from sagasmith.schemas.persistence import RetconAuditRecord

_RETCON_EFFECTS = (
    "Retcon will perform a state rewind to the prior safe checkpoint, rebuild "
    "affected transcript/mechanics/vault/memory outputs from canonical sources, "
    "preserve audit retention for removed canon, and enforce canonical exclusion "
    "after success."
)


class RetconBlockedError(RuntimeError):
    """Raised when a retcon cannot safely proceed without repair."""

    def __init__(self, message: str, repair_guidance: str) -> None:
        super().__init__(message)
        self.repair_guidance = repair_guidance


@dataclass(frozen=True)
class RetconCandidate:
    turn_id: str
    completed_at: str
    summary: str


@dataclass(frozen=True)
class RetconPreview:
    selected_turn_id: str
    affected_turn_ids: list[str]
    prior_checkpoint_id: str
    transcript_count: int
    roll_count: int
    vault_paths: list[str]
    confirmation_token: str
    effects: str


@dataclass(frozen=True)
class RetconResult:
    selected_turn_id: str
    affected_turn_ids: list[str]
    prior_checkpoint_id: str
    audit_id: str
    message: str


@dataclass
class RetconService:
    """Deterministic retcon service over canonical SQLite turn records."""

    conn: sqlite3.Connection
    campaign_id: str

    def list_candidates(self, *, limit: int = 5) -> list[RetconCandidate]:
        turns = TurnRecordRepository(self.conn).list_recent_completed(self.campaign_id, limit=limit)
        return [
            RetconCandidate(
                turn_id=turn.turn_id,
                completed_at=turn.completed_at,
                summary=_summary_for_turn(self.conn, turn.turn_id),
            )
            for turn in turns
        ]

    def preview(self, selected_turn_id: str) -> RetconPreview:
        selected = TurnRecordRepository(self.conn).get(selected_turn_id)
        if selected is None or selected.campaign_id != self.campaign_id:
            raise RetconBlockedError(
                f"Turn {selected_turn_id} is not part of campaign {self.campaign_id}.",
                "Repair by selecting an eligible completed turn from the current campaign.",
            )
        if selected.status != "complete":
            raise RetconBlockedError(
                f"Turn {selected_turn_id} is not complete and cannot be retconned.",
                "Repair by choosing a completed canonical turn or resolving the incomplete turn first.",
            )

        prior_checkpoint_id = _prior_final_checkpoint(self.conn, self.campaign_id, selected.completed_at)
        if prior_checkpoint_id is None:
            raise RetconBlockedError(
                f"No prior final checkpoint exists before turn {selected_turn_id}.",
                "Repair by running checkpoint repair or choosing a later completed turn with a prior final checkpoint.",
            )

        affected_turns = TurnRecordRepository(self.conn).list_affected_suffix(
            self.campaign_id,
            selected_turn_id,
        )
        affected_turn_ids = [turn.turn_id for turn in affected_turns]
        if not affected_turn_ids:
            raise RetconBlockedError(
                f"No canonical suffix could be identified for turn {selected_turn_id}.",
                "Repair by rebuilding turn metadata before retrying retcon.",
            )

        return RetconPreview(
            selected_turn_id=selected_turn_id,
            affected_turn_ids=affected_turn_ids,
            prior_checkpoint_id=prior_checkpoint_id,
            transcript_count=_count_rows_for_turns(self.conn, "transcript_entries", affected_turn_ids),
            roll_count=_count_rows_for_turns(self.conn, "roll_logs", affected_turn_ids),
            vault_paths=_vault_paths(self.conn, affected_turn_ids),
            confirmation_token=f"RETCON {selected_turn_id}",
            effects=_RETCON_EFFECTS,
        )

    def confirm(
        self,
        selected_turn_id: str,
        confirmation_token: str,
        reason: str = "player_retcon",
    ) -> RetconResult:
        preview = self.preview(selected_turn_id)
        if confirmation_token != preview.confirmation_token:
            raise RetconBlockedError(
                f"Confirmation token for turn {selected_turn_id} did not match.",
                f"Repair by typing the exact token: {preview.confirmation_token}",
            )
        audit_id = f"retcon-{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        try:
            self.conn.execute("BEGIN")
            TurnRecordRepository(self.conn).mark_retconned(preview.affected_turn_ids)
            RetconAuditRepository(self.conn).append(
                RetconAuditRecord(
                    retcon_id=audit_id,
                    campaign_id=self.campaign_id,
                    selected_turn_id=selected_turn_id,
                    affected_turn_ids=preview.affected_turn_ids,
                    prior_checkpoint_id=preview.prior_checkpoint_id,
                    confirmation_token=confirmation_token,
                    reason=reason,
                    created_at=now,
                )
            )
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        return RetconResult(
            selected_turn_id=selected_turn_id,
            affected_turn_ids=preview.affected_turn_ids,
            prior_checkpoint_id=preview.prior_checkpoint_id,
            audit_id=audit_id,
            message=(
                f"Retcon complete for {selected_turn_id}; "
                f"{len(preview.affected_turn_ids)} turn(s) excluded from canon."
            ),
        )


def _summary_for_turn(conn: sqlite3.Connection, turn_id: str) -> str:
    entries = TranscriptRepository(conn).list_for_turn(turn_id)
    for entry in reversed(entries):
        if entry.kind == "narration_final" and entry.content.strip():
            return _concise(entry.content)
    for entry in reversed(entries):
        if entry.content.strip():
            return _concise(entry.content)
    return "No transcript summary available."


def _concise(value: str, *, max_chars: int = 160) -> str:
    line = " ".join(value.strip().split())
    if len(line) <= max_chars:
        return line
    return line[: max_chars - 1].rstrip() + "…"


def _prior_final_checkpoint(conn: sqlite3.Connection, campaign_id: str, before_completed_at: str) -> str | None:
    row = conn.execute(
        """
        SELECT cr.checkpoint_id
          FROM checkpoint_refs AS cr
          JOIN turn_records AS tr ON tr.turn_id = cr.turn_id
         WHERE tr.campaign_id = ?
           AND tr.status = 'complete'
           AND tr.completed_at < ?
           AND cr.kind = 'final'
         ORDER BY tr.completed_at DESC, cr.created_at DESC
         LIMIT 1
        """,
        (campaign_id, before_completed_at),
    ).fetchone()
    return row[0] if row is not None else None


def _count_rows_for_turns(conn: sqlite3.Connection, table: str, turn_ids: list[str]) -> int:
    if not turn_ids:
        return 0
    placeholders = ", ".join("?" for _ in turn_ids)
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE turn_id IN ({placeholders})",
        tuple(turn_ids),
    ).fetchone()
    return int(row[0]) if row is not None else 0


def _vault_paths(conn: sqlite3.Connection, turn_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for record in VaultWriteAuditRepository(conn).list_for_turns(turn_ids):
        if record.vault_path not in seen:
            seen.add(record.vault_path)
            paths.append(record.vault_path)
    return paths
