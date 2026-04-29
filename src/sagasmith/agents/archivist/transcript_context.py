"""Recent transcript context retrieval for Phase 6 memory packet stubs."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from sagasmith.persistence.repositories import TranscriptRepository


@dataclass(frozen=True)
class TranscriptContextEntry:
    """Compact transcript line selected for memory packet context."""

    turn_id: str
    kind: str
    content: str
    sequence: int

    def format_for_memory(self) -> str:
        """Return a deterministic, compact memory packet line."""

        return f"{self.turn_id}:{self.sequence}:{self.kind}: {self.content}"


def get_recent_transcript_context(
    conn: sqlite3.Connection | None,
    *,
    campaign_id: str,
    limit: int = 8,
) -> list[TranscriptContextEntry]:
    """Return recent transcript entries for a campaign from SQLite.

    Missing persistence is not an error in Phase 6: tests and early graph smoke
    paths can run without a campaign database, so this degrades to an empty
    context list while the packet builder records a retrieval note.
    """

    if conn is None or limit <= 0:
        return []
    try:
        records = TranscriptRepository(conn).list_canonical_for_campaign(campaign_id, limit=limit)
    except sqlite3.Error:
        return []
    entries = [
        TranscriptContextEntry(
            turn_id=record.turn_id,
            kind=record.kind,
            content=record.content,
            sequence=record.sequence,
        )
        for record in records
    ]
    return entries


def format_transcript_context(entries: list[TranscriptContextEntry]) -> list[str]:
    """Format transcript rows for MemoryPacket.recent_turns."""

    return [entry.format_for_memory() for entry in entries]
