"""Tests for persistence schemas, migrations, and db utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.persistence.db import campaign_db, current_schema_version, open_campaign_db
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.export import export_all_schemas
from sagasmith.schemas.persistence import (
    CheckpointRef,
    CostLogRecord,
    StateDeltaRecord,
    TranscriptEntry,
    TurnRecord,
)


@pytest.mark.smoke
def test_apply_migrations_creates_tables(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    with campaign_db(path) as conn:
            applied = apply_migrations(conn)
            # 0001_initial.sql (v1), 0002_campaign_and_settings.sql (v2),
            # 0003_onboarding_records.sql (v3), 0004_safety_events.sql (v4),
            # and 0005_agent_skill_log.sql (v5) are all applied on a fresh DB.
            assert applied == [1, 2, 3, 4, 5]
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            assert {
                "schema_version",
                "turn_records",
                "transcript_entries",
                "roll_logs",
                "provider_logs",
                "cost_logs",
                "state_deltas",
                "checkpoint_refs",
                "campaigns",
                "settings",
            } <= tables


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    with campaign_db(path) as conn:
        apply_migrations(conn)
        second = apply_migrations(conn)
        assert second == []


def test_current_schema_version_zero_before_migration(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    conn = open_campaign_db(path)
    assert current_schema_version(conn) == 0
    conn.close()


def test_current_schema_version_one_after_migration(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    with campaign_db(path) as conn:
        apply_migrations(conn)
        # All migrations applied: v1 (initial), v2 (campaign_and_settings), v3 (onboarding), v4 (safety_events), v5 (agent_skill_log).
        assert current_schema_version(conn) == 5


def test_apply_migrations_persists_schema_version_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    with campaign_db(path) as conn:
        # v1, v2, v3, v4, and v5 are applied on a fresh DB.
        assert apply_migrations(conn) == [1, 2, 3, 4, 5]

    with campaign_db(path) as conn:
        assert current_schema_version(conn) == 5
        assert apply_migrations(conn) == []


def test_open_campaign_db_enables_foreign_keys(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    conn = open_campaign_db(path)
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result is not None
    assert result[0] == 1
    conn.close()


def test_persistence_schemas_round_trip() -> None:
    tr = TurnRecord(
        turn_id="t1",
        campaign_id="c1",
        session_id="s1",
        status="complete",
        started_at="2026-04-26T12:00:00Z",
        completed_at="2026-04-26T12:01:00Z",
        schema_version=1,
    )
    assert TurnRecord.model_validate(tr.model_dump(mode="json")) == tr

    cl = CostLogRecord(
        turn_id="t1",
        provider="fake",
        model="m",
        agent_name="a",
        cost_usd=0.01,
        cost_is_approximate=True,
        tokens_prompt=10,
        tokens_completion=5,
        warnings_fired=["70"],
        spent_usd_after=0.01,
        timestamp="2026-04-26T12:00:00Z",
    )
    assert CostLogRecord.model_validate(cl.model_dump(mode="json")) == cl

    te = TranscriptEntry(
        turn_id="t1",
        kind="player_input",
        content="hello",
        sequence=0,
        created_at="2026-04-26T12:00:00Z",
    )
    assert TranscriptEntry.model_validate(te.model_dump(mode="json")) == te

    cr = CheckpointRef(
        checkpoint_id="cp1",
        turn_id="t1",
        kind="final",
        created_at="2026-04-26T12:00:00Z",
    )
    assert CheckpointRef.model_validate(cr.model_dump(mode="json")) == cr

    sd = StateDeltaRecord(
        turn_id="t1",
        delta_id="d1",
        source="rules",
        path="hp",
        operation="increment",
        value_json="-3",
        reason="damage",
        applied_at="2026-04-26T12:00:00Z",
    )
    assert StateDeltaRecord.model_validate(sd.model_dump(mode="json")) == sd


@pytest.mark.smoke
def test_schema_export_count_is_25(tmp_path: Path) -> None:
    out = tmp_path / "schemas"
    paths = export_all_schemas(out)
    # Phase 3 Plan 01 added CampaignManifest and ProviderSettings (total: 27).
    assert len(paths) == 27
    names = {p.name.removesuffix(".schema.json") for p in paths}
    assert {
        "CostLogRecord",
        "TurnRecord",
        "CheckpointRef",
        "TranscriptEntry",
        "StateDeltaRecord",
        "CampaignManifest",
        "ProviderSettings",
    } <= names
