"""Tests for migration 0004_safety_events (SAFE-06 schema guarantees)."""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.persistence.migrations import apply_migrations


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_migration_0004_creates_safety_events_table() -> None:
    """Fresh in-memory DB → apply_migrations → safety_events table exists with all 8 columns."""
    conn = _make_conn()
    applied = apply_migrations(conn)
    assert 4 in applied

    cols = conn.execute("PRAGMA table_info(safety_events)").fetchall()
    col_names = {c[1] for c in cols}
    assert col_names == {
        "event_id",
        "campaign_id",
        "turn_id",
        "kind",
        "policy_ref",
        "action_taken",
        "timestamp",
        "visibility",
    }, f"Unexpected columns: {col_names}"


def test_safety_events_check_visibility_rejects_gm_only() -> None:
    """INSERT a row with visibility='gm_only' → sqlite3.IntegrityError (SAFE-06)."""
    conn = _make_conn()
    apply_migrations(conn)

    # Insert a valid campaign first to satisfy FK
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("camp-test", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO safety_events "
            "(event_id, campaign_id, turn_id, kind, policy_ref, action_taken, timestamp, visibility) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ev1", "camp-test", None, "pause", None, "player requested pause", "2026-01-01T00:00:00Z", "gm_only"),
        )
        conn.commit()


def test_safety_events_check_kind_rejects_unknown() -> None:
    """INSERT with kind='danger' → sqlite3.IntegrityError."""
    conn = _make_conn()
    apply_migrations(conn)

    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("camp-test", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO safety_events "
            "(event_id, campaign_id, turn_id, kind, policy_ref, action_taken, timestamp, visibility) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ev2", "camp-test", None, "danger", None, "some action", "2026-01-01T00:00:00Z", "player_visible"),
        )
        conn.commit()


def test_safety_events_fk_to_campaigns() -> None:
    """INSERT with unknown campaign_id → sqlite3.IntegrityError with FK PRAGMA on."""
    conn = _make_conn()
    apply_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO safety_events "
            "(event_id, campaign_id, turn_id, kind, policy_ref, action_taken, timestamp, visibility) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ev3", "nonexistent-campaign", None, "pause", None, "player requested pause", "2026-01-01T00:00:00Z", "player_visible"),
        )
        conn.commit()
