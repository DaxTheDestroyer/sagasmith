"""Tests for CanonicalTurnHistory — the canonical-status predicate owner."""

from __future__ import annotations

import sqlite3

from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    CheckpointRefRepository,
    TranscriptRepository,
    TurnRecordRepository,
)
from sagasmith.persistence.turn_history import CanonicalTurnHistory
from sagasmith.schemas.persistence import (
    CheckpointRef,
    TranscriptEntry,
    TurnRecord,
    TurnStatus,
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn


def _turn(
    turn_id: str,
    *,
    campaign_id: str = "camp-1",
    session_id: str = "session_001",
    status: str = TurnStatus.CANONICAL,
    completed_at: str = "2026-04-01T10:00:00Z",
    started_at: str = "2026-04-01T09:55:00Z",
) -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        campaign_id=campaign_id,
        session_id=session_id,
        status=status,  # type: ignore[arg-type]
        started_at=started_at,
        completed_at=completed_at,
        schema_version=1,
    )


def _insert(conn: sqlite3.Connection, *turns: TurnRecord) -> None:
    repo = TurnRecordRepository(conn)
    for turn in turns:
        repo.upsert(turn)


def _checkpoint(
    checkpoint_id: str,
    turn_id: str,
    *,
    kind: str = "final",
    created_at: str = "2026-04-01T10:01:00Z",
) -> CheckpointRef:
    return CheckpointRef(
        checkpoint_id=checkpoint_id,
        turn_id=turn_id,
        kind=kind,  # type: ignore[arg-type]
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# latest_turn_id
# ---------------------------------------------------------------------------


def test_latest_turn_id_returns_most_recent_canonical() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", completed_at="2026-04-01T11:00:00Z"),
    )
    assert CanonicalTurnHistory(conn).latest_turn_id("camp-1") == "t2"


def test_latest_turn_id_ignores_retconned_even_if_newer() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", status=TurnStatus.RETCONNED, completed_at="2026-04-01T12:00:00Z"),
    )
    assert CanonicalTurnHistory(conn).latest_turn_id("camp-1") == "t1"


def test_latest_turn_id_includes_retconned_when_opted_in() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", status=TurnStatus.RETCONNED, completed_at="2026-04-01T12:00:00Z"),
    )
    result = CanonicalTurnHistory(conn).latest_turn_id("camp-1", include_retconned=True)
    assert result == "t2"


def test_latest_turn_id_returns_none_for_empty_campaign() -> None:
    conn = _make_conn()
    assert CanonicalTurnHistory(conn).latest_turn_id("camp-empty") is None


def test_latest_turn_id_returns_none_when_all_retconned() -> None:
    conn = _make_conn()
    _insert(conn, _turn("t1", status=TurnStatus.RETCONNED))
    assert CanonicalTurnHistory(conn).latest_turn_id("camp-1") is None


# ---------------------------------------------------------------------------
# latest_session_id
# ---------------------------------------------------------------------------


def test_latest_session_id_returns_session_of_newest_canonical_turn() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", session_id="session_002", completed_at="2026-04-01T11:00:00Z"),
    )
    assert CanonicalTurnHistory(conn).latest_session_id("camp-1") == "session_002"


def test_latest_session_id_ignores_retconned() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001", completed_at="2026-04-01T10:00:00Z"),
        _turn(
            "t2",
            session_id="session_002",
            status=TurnStatus.RETCONNED,
            completed_at="2026-04-01T12:00:00Z",
        ),
    )
    assert CanonicalTurnHistory(conn).latest_session_id("camp-1") == "session_001"


def test_latest_session_id_returns_none_for_empty_campaign() -> None:
    conn = _make_conn()
    assert CanonicalTurnHistory(conn).latest_session_id("camp-empty") is None


# ---------------------------------------------------------------------------
# session_turn_ids
# ---------------------------------------------------------------------------


def test_session_turn_ids_returns_ordered_canonical_turns() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", session_id="session_001", completed_at="2026-04-01T10:30:00Z"),
        _turn("t3", session_id="session_002", completed_at="2026-04-01T11:00:00Z"),
    )
    assert CanonicalTurnHistory(conn).session_turn_ids("camp-1", "session_001") == [
        "t1",
        "t2",
    ]


def test_session_turn_ids_excludes_retconned_turns() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001", completed_at="2026-04-01T10:00:00Z"),
        _turn(
            "t2",
            session_id="session_001",
            status=TurnStatus.RETCONNED,
            completed_at="2026-04-01T10:30:00Z",
        ),
    )
    assert CanonicalTurnHistory(conn).session_turn_ids("camp-1", "session_001") == ["t1"]


def test_session_turn_ids_returns_empty_for_unknown_session() -> None:
    conn = _make_conn()
    assert CanonicalTurnHistory(conn).session_turn_ids("camp-1", "session_999") == []


# ---------------------------------------------------------------------------
# session_ids_for_campaign (covers runtime.py:132 bug)
# ---------------------------------------------------------------------------


def test_session_ids_for_campaign_excludes_retconned_only_sessions() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001", completed_at="2026-04-01T10:00:00Z"),
        _turn(
            "t2",
            session_id="session_002",
            status=TurnStatus.RETCONNED,
            completed_at="2026-04-01T11:00:00Z",
        ),
    )
    result = CanonicalTurnHistory(conn).session_ids_for_campaign("camp-1")
    assert result == ["session_001"]


def test_session_ids_for_campaign_with_include_retconned_returns_all() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", session_id="session_001"),
        _turn("t2", session_id="session_002", status=TurnStatus.RETCONNED),
    )
    result = set(
        CanonicalTurnHistory(conn).session_ids_for_campaign("camp-1", include_retconned=True)
    )
    assert result == {"session_001", "session_002"}


def test_session_ids_for_campaign_returns_empty_for_empty_campaign() -> None:
    conn = _make_conn()
    assert CanonicalTurnHistory(conn).session_ids_for_campaign("camp-empty") == []


# ---------------------------------------------------------------------------
# scrollback
# ---------------------------------------------------------------------------


def test_scrollback_returns_canonical_entries_in_chronological_order() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", completed_at="2026-04-01T11:00:00Z"),
    )
    tr = TranscriptRepository(conn)
    tr.append(
        TranscriptEntry(
            turn_id="t1",
            kind="player_input",
            content="hello",
            sequence=0,
            created_at="2026-04-01T10:00:00Z",
        )
    )
    tr.append(
        TranscriptEntry(
            turn_id="t2",
            kind="narration_final",
            content="world",
            sequence=0,
            created_at="2026-04-01T11:00:00Z",
        )
    )
    entries = CanonicalTurnHistory(conn).scrollback("camp-1")
    assert [e.kind for e in entries] == ["player_input", "narration_final"]
    assert [e.content for e in entries] == ["hello", "world"]


def test_scrollback_excludes_retconned_turns() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", status=TurnStatus.RETCONNED, completed_at="2026-04-01T10:00:00Z"),
        _turn("t2", completed_at="2026-04-01T11:00:00Z"),
    )
    tr = TranscriptRepository(conn)
    tr.append(
        TranscriptEntry(
            turn_id="t1",
            kind="narration_final",
            content="retconned",
            sequence=0,
            created_at="2026-04-01T10:00:00Z",
        )
    )
    tr.append(
        TranscriptEntry(
            turn_id="t2",
            kind="narration_final",
            content="canonical",
            sequence=0,
            created_at="2026-04-01T11:00:00Z",
        )
    )
    entries = CanonicalTurnHistory(conn).scrollback("camp-1")
    assert len(entries) == 1
    assert entries[0].content == "canonical"


def test_scrollback_respects_limit() -> None:
    conn = _make_conn()
    _insert(conn, _turn("t1"))
    tr = TranscriptRepository(conn)
    for i in range(10):
        tr.append(
            TranscriptEntry(
                turn_id="t1",
                kind="system_note",
                content=f"line {i}",
                sequence=i,
                created_at="2026-04-01T10:00:00Z",
            )
        )
    entries = CanonicalTurnHistory(conn).scrollback("camp-1", limit=3)
    assert len(entries) == 3


def test_scrollback_returns_empty_for_zero_limit() -> None:
    conn = _make_conn()
    _insert(conn, _turn("t1"))
    assert CanonicalTurnHistory(conn).scrollback("camp-1", limit=0) == []


# ---------------------------------------------------------------------------
# latest_sync_warning
# ---------------------------------------------------------------------------


def test_latest_sync_warning_returns_warning_from_canonical_turn() -> None:
    conn = _make_conn()
    repo = TurnRecordRepository(conn)
    turn = _turn("t1", completed_at="2026-04-01T10:00:00Z")
    repo.upsert(turn)
    conn.execute("UPDATE turn_records SET sync_warning = 'vault out of sync' WHERE turn_id = 't1'")
    result = CanonicalTurnHistory(conn).latest_sync_warning("camp-1", "session_001")
    assert result == "vault out of sync"


def test_latest_sync_warning_ignores_retconned_turn() -> None:
    conn = _make_conn()
    repo = TurnRecordRepository(conn)
    repo.upsert(_turn("t1", status=TurnStatus.RETCONNED, completed_at="2026-04-01T12:00:00Z"))
    conn.execute("UPDATE turn_records SET sync_warning = 'stale' WHERE turn_id = 't1'")
    assert CanonicalTurnHistory(conn).latest_sync_warning("camp-1", "session_001") is None


def test_latest_sync_warning_returns_none_for_blank_warning() -> None:
    conn = _make_conn()
    repo = TurnRecordRepository(conn)
    repo.upsert(_turn("t1"))
    conn.execute("UPDATE turn_records SET sync_warning = '   ' WHERE turn_id = 't1'")
    assert CanonicalTurnHistory(conn).latest_sync_warning("camp-1", "session_001") is None


def test_latest_sync_warning_returns_none_when_no_turns() -> None:
    conn = _make_conn()
    assert CanonicalTurnHistory(conn).latest_sync_warning("camp-1", "session_001") is None


# ---------------------------------------------------------------------------
# prior_final_checkpoint
# ---------------------------------------------------------------------------


def test_prior_final_checkpoint_returns_most_recent_canonical_checkpoint_before_timestamp() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", completed_at="2026-04-01T09:00:00Z"),
        _turn("t2", completed_at="2026-04-01T10:00:00Z"),
    )
    cr = CheckpointRefRepository(conn)
    cr.append(_checkpoint("cp1", "t1", created_at="2026-04-01T09:01:00Z"))
    cr.append(_checkpoint("cp2", "t2", created_at="2026-04-01T10:01:00Z"))

    # Select t2 for retcon; prior final checkpoint should be cp1 (before t2.completed_at)
    result = CanonicalTurnHistory(conn).prior_final_checkpoint("camp-1", "2026-04-01T10:00:00Z")
    assert result == "cp1"


def test_prior_final_checkpoint_excludes_retconned_turns() -> None:
    conn = _make_conn()
    _insert(
        conn,
        _turn("t1", status=TurnStatus.RETCONNED, completed_at="2026-04-01T09:00:00Z"),
    )
    cr = CheckpointRefRepository(conn)
    cr.append(_checkpoint("cp1", "t1"))

    result = CanonicalTurnHistory(conn).prior_final_checkpoint("camp-1", "2026-04-01T10:00:00Z")
    assert result is None


def test_prior_final_checkpoint_returns_none_when_no_prior_exists() -> None:
    conn = _make_conn()
    assert (
        CanonicalTurnHistory(conn).prior_final_checkpoint("camp-1", "2026-04-01T10:00:00Z") is None
    )
