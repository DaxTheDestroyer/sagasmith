"""Canonical turn history reads — single owner of the canonical-status predicate."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from sagasmith.schemas.persistence import TranscriptEntry, TurnStatus


@dataclass(frozen=True)
class SessionTranscriptRow:
    turn_id: str
    kind: str
    content: str
    sequence: int


@dataclass(frozen=True)
class SessionRollRow:
    roll_id: str
    die: str
    natural: int
    modifier: int
    total: int
    dc: int | None


@dataclass(frozen=True)
class SessionPageSource:
    transcript_rows: tuple[SessionTranscriptRow, ...]
    roll_rows: tuple[SessionRollRow, ...]


@dataclass(frozen=True)
class CanonicalTurnHistory:
    conn: sqlite3.Connection

    def latest_turn_id(self, campaign_id: str, *, include_retconned: bool = False) -> str | None:
        """Return most recent canonical turn_id for the campaign."""
        status_filter = "" if include_retconned else f"AND status = '{TurnStatus.CANONICAL}'"
        row = self.conn.execute(
            f"""
            SELECT turn_id FROM turn_records
             WHERE campaign_id = ?
               {status_filter}
             ORDER BY completed_at DESC, turn_id DESC
             LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        return row[0] if row else None

    def latest_session_id(self, campaign_id: str, *, include_retconned: bool = False) -> str | None:
        """Return session_id of the most recent canonical turn for the campaign."""
        status_filter = "" if include_retconned else f"AND status = '{TurnStatus.CANONICAL}'"
        row = self.conn.execute(
            f"""
            SELECT session_id FROM turn_records
             WHERE campaign_id = ?
               {status_filter}
             ORDER BY completed_at DESC, turn_id DESC
             LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        return row[0] if row else None

    def session_turn_ids(
        self,
        campaign_id: str,
        session_id: str,
        *,
        include_retconned: bool = False,
    ) -> list[str]:
        """Return ordered canonical turn_ids for a session."""
        status_filter = "" if include_retconned else f"AND status = '{TurnStatus.CANONICAL}'"
        rows = self.conn.execute(
            f"""
            SELECT turn_id FROM turn_records
             WHERE campaign_id = ? AND session_id = ?
               {status_filter}
             ORDER BY completed_at, started_at, turn_id
            """,
            (campaign_id, session_id),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def session_page_source(
        self,
        campaign_id: str,
        session_id: str,
        *,
        include_retconned: bool = False,
    ) -> SessionPageSource:
        """Return ordered source rows for an end-of-session vault page."""
        status_filter = "" if include_retconned else f"AND tr.status = '{TurnStatus.CANONICAL}'"
        transcript_rows = self.conn.execute(
            f"""
            SELECT te.turn_id, te.kind, te.content, te.sequence
              FROM transcript_entries AS te
              JOIN turn_records AS tr ON tr.turn_id = te.turn_id
             WHERE tr.campaign_id = ? AND tr.session_id = ?
               {status_filter}
             ORDER BY tr.completed_at, tr.started_at, tr.turn_id, te.sequence
            """,
            (campaign_id, session_id),
        ).fetchall()
        roll_rows = self.conn.execute(
            f"""
            SELECT rl.roll_id, rl.die, rl.natural, rl.modifier, rl.total, rl.dc
              FROM roll_logs AS rl
              JOIN turn_records AS tr ON tr.turn_id = rl.turn_id
             WHERE tr.campaign_id = ? AND tr.session_id = ?
               {status_filter}
             ORDER BY tr.completed_at, tr.started_at, tr.turn_id, rl.timestamp, rl.roll_id
            """,
            (campaign_id, session_id),
        ).fetchall()
        return SessionPageSource(
            transcript_rows=tuple(
                SessionTranscriptRow(
                    turn_id=str(row[0]),
                    kind=str(row[1]),
                    content=str(row[2]),
                    sequence=int(row[3]),
                )
                for row in transcript_rows
            ),
            roll_rows=tuple(
                SessionRollRow(
                    roll_id=str(row[0]),
                    die=str(row[1]),
                    natural=int(row[2]),
                    modifier=int(row[3]),
                    total=int(row[4]),
                    dc=int(row[5]) if row[5] is not None else None,
                )
                for row in roll_rows
            ),
        )

    def session_ids_for_campaign(
        self, campaign_id: str, *, include_retconned: bool = False
    ) -> list[str]:
        """Return distinct session_ids that have at least one canonical turn."""
        status_filter = "" if include_retconned else f"AND status = '{TurnStatus.CANONICAL}'"
        rows = self.conn.execute(
            f"""
            SELECT DISTINCT session_id FROM turn_records
             WHERE campaign_id = ?
               {status_filter}
            """,
            (campaign_id,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def scrollback(
        self,
        campaign_id: str,
        *,
        limit: int = 50,
        include_retconned: bool = False,
    ) -> list[TranscriptEntry]:
        """Return last ``limit`` canonical transcript entries in chronological order."""
        if limit <= 0:
            return []
        status_filter = "" if include_retconned else f"AND tr.status = '{TurnStatus.CANONICAL}'"
        rows = self.conn.execute(
            f"""
            SELECT te.turn_id, te.kind, te.content, te.sequence, te.created_at
              FROM transcript_entries AS te
              JOIN turn_records AS tr ON tr.turn_id = te.turn_id
             WHERE tr.campaign_id = ?
               {status_filter}
             ORDER BY tr.completed_at DESC, te.sequence DESC
             LIMIT ?
            """,
            (campaign_id, limit),
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

    def latest_sync_warning(
        self,
        campaign_id: str,
        session_id: str,
        *,
        include_retconned: bool = False,
    ) -> str | None:
        """Return sync_warning from the latest canonical turn in the given session."""
        status_filter = "" if include_retconned else f"AND status = '{TurnStatus.CANONICAL}'"
        row = self.conn.execute(
            f"""
            SELECT sync_warning FROM turn_records
             WHERE campaign_id = ? AND session_id = ?
               {status_filter}
             ORDER BY completed_at DESC, turn_id DESC
             LIMIT 1
            """,
            (campaign_id, session_id),
        ).fetchone()
        if row is None:
            return None
        value = row[0]
        return value if isinstance(value, str) and value.strip() else None

    def prior_final_checkpoint(
        self,
        campaign_id: str,
        before_completed_at: str,
        *,
        include_retconned: bool = False,
    ) -> str | None:
        """Return checkpoint_id of the most recent canonical final checkpoint
        strictly before ``before_completed_at``, or None."""
        status_filter = "" if include_retconned else f"AND tr.status = '{TurnStatus.CANONICAL}'"
        row = self.conn.execute(
            f"""
            SELECT cr.checkpoint_id
              FROM checkpoint_refs AS cr
              JOIN turn_records AS tr ON tr.turn_id = cr.turn_id
             WHERE tr.campaign_id = ?
               {status_filter}
               AND tr.completed_at < ?
               AND cr.kind = 'final'
             ORDER BY tr.completed_at DESC, cr.created_at DESC
             LIMIT 1
            """,
            (campaign_id, before_completed_at),
        ).fetchone()
        return row[0] if row is not None else None
