"""Tests for transcript context retrieval used by MemoryPacket stubs."""

from __future__ import annotations

import sqlite3

from sagasmith.agents.archivist.transcript_context import (
    format_transcript_context,
    get_recent_transcript_context,
)
from sagasmith.persistence.migrations import apply_migrations


def _conn_with_transcript() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    for index in range(3):
        turn_id = f"turn_{index:06d}"
        conn.execute(
            "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                turn_id,
                "cmp_001",
                "sess_001",
                "complete",
                f"2026-01-01T00:0{index}:00Z",
                f"2026-01-01T00:0{index}:30Z",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
            (turn_id, "narration_final", f"Marcus mentioned clue {index}.", 0, "2026-01-01T00:00:00Z"),
        )
    conn.commit()
    return conn


def test_recent_transcript_context_returns_newest_rows_in_chronological_order() -> None:
    conn = _conn_with_transcript()

    entries = get_recent_transcript_context(conn, campaign_id="cmp_001", limit=2)

    assert [entry.turn_id for entry in entries] == ["turn_000001", "turn_000002"]
    assert format_transcript_context(entries) == [
        "turn_000001:0:narration_final: Marcus mentioned clue 1.",
        "turn_000002:0:narration_final: Marcus mentioned clue 2.",
    ]


def test_recent_transcript_context_degrades_to_empty_without_sqlite() -> None:
    assert get_recent_transcript_context(None, campaign_id="cmp_001") == []
