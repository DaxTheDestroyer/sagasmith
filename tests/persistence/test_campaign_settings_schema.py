"""Tests for the 0002_campaign_and_settings migration."""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.persistence.migrations import apply_migrations, current_schema_version


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_migration_0002_creates_campaigns_and_settings() -> None:
    conn = _make_conn()
    applied = apply_migrations(conn)
    # 0001-0008 should be applied on a fresh DB
    assert applied == [1, 2, 3, 4, 5, 6, 7, 8]
    assert current_schema_version(conn) == 8

    # campaigns table should have 6 columns
    campaign_cols = conn.execute("PRAGMA table_info(campaigns)").fetchall()
    assert len(campaign_cols) == 6, f"Expected 6 columns, got: {[c[1] for c in campaign_cols]}"

    # settings table should have 4 columns
    settings_cols = conn.execute("PRAGMA table_info(settings)").fetchall()
    assert len(settings_cols) == 4, f"Expected 4 columns, got: {[c[1] for c in settings_cols]}"


def test_settings_foreign_key_enforced() -> None:
    conn = _make_conn()
    apply_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO settings (campaign_id, key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("nonexistent-campaign-id", "provider", '{"some":"value"}', "2026-01-01T00:00:00Z"),
        )
        conn.commit()
