"""Tests for SafetyEventService (SAFE-04, SAFE-05, SAFE-06)."""

from __future__ import annotations

import sqlite3
import time

import pytest

from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import SafetyEventRepository
from sagasmith.services.errors import TrustServiceError
from sagasmith.services.safety import SafetyEventService

_CAMPAIGN_ID = "test-abc12345"


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@pytest.fixture
def campaign_conn() -> sqlite3.Connection:
    """In-memory DB, migrations applied, one campaign row inserted."""
    conn = _make_conn()
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (_CAMPAIGN_ID, "Test Campaign", "test-campaign", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    conn.commit()
    return conn


def test_log_pause_creates_event_row(campaign_conn: sqlite3.Connection) -> None:
    service = SafetyEventService(conn=campaign_conn)
    record = service.log_pause(campaign_id=_CAMPAIGN_ID)

    assert record.kind == "pause"
    assert record.policy_ref is None
    assert record.action_taken == "player requested pause"
    assert record.visibility == "player_visible"
    assert record.campaign_id == _CAMPAIGN_ID

    # Confirm it's in the DB
    rows = SafetyEventRepository(campaign_conn).list_for_campaign(_CAMPAIGN_ID)
    assert len(rows) == 1
    assert rows[0].kind == "pause"


def test_log_line_requires_non_empty_topic(campaign_conn: sqlite3.Connection) -> None:
    service = SafetyEventService(conn=campaign_conn)
    with pytest.raises(ValueError, match="/line requires a topic"):
        service.log_line(campaign_id=_CAMPAIGN_ID, topic="  ")


def test_log_line_caps_topic_at_200_chars(campaign_conn: sqlite3.Connection) -> None:
    service = SafetyEventService(conn=campaign_conn)
    long_topic = "x" * 201
    with pytest.raises(ValueError, match="too long"):
        service.log_line(campaign_id=_CAMPAIGN_ID, topic=long_topic)


def test_log_line_records_policy_ref_and_action(campaign_conn: sqlite3.Connection) -> None:
    service = SafetyEventService(conn=campaign_conn)
    record = service.log_line(campaign_id=_CAMPAIGN_ID, topic="graphic_violence")

    assert record.kind == "line"
    assert record.policy_ref == "graphic_violence"
    assert record.action_taken == "redlined:graphic_violence"
    assert record.visibility == "player_visible"


def test_log_fallback_reserved_for_phase6(campaign_conn: sqlite3.Connection) -> None:
    """log_fallback exists and produces a row with kind='fallback'."""
    service = SafetyEventService(conn=campaign_conn)
    record = service.log_fallback(campaign_id=_CAMPAIGN_ID, reason="retry failed")

    assert record.kind == "fallback"
    assert record.action_taken == "fallback:retry failed"
    # Also assert the method exists on the service (future consumer needs it)
    assert hasattr(service, "log_fallback")


def test_log_event_rejected_if_secret_shaped(campaign_conn: sqlite3.Connection) -> None:
    """SAFE-06 + QA-04: secret-shaped topic is rejected, DB row count unchanged."""
    service = SafetyEventService(conn=campaign_conn)

    row_count_before = campaign_conn.execute("SELECT COUNT(*) FROM safety_events").fetchone()[0]

    with pytest.raises(TrustServiceError, match="safety event rejected by redaction canary"):
        service.log_line(campaign_id=_CAMPAIGN_ID, topic="sk-proj-leakybadkey1234567890abcdefgh")

    row_count_after = campaign_conn.execute("SELECT COUNT(*) FROM safety_events").fetchone()[0]
    assert row_count_after == row_count_before


def test_list_recent_orders_by_timestamp_desc(campaign_conn: sqlite3.Connection) -> None:
    """list_recent returns events newest-first."""
    service = SafetyEventService(conn=campaign_conn)
    # Log 3 events with small delays to ensure different timestamps
    r1 = service.log_pause(campaign_id=_CAMPAIGN_ID)
    time.sleep(0.01)
    r2 = service.log_line(campaign_id=_CAMPAIGN_ID, topic="topic_a")
    time.sleep(0.01)
    r3 = service.log_line(campaign_id=_CAMPAIGN_ID, topic="topic_b")

    results = service.list_recent(_CAMPAIGN_ID)
    assert len(results) == 3
    # Newest-first: r3, r2, r1
    assert results[0].event_id == r3.event_id
    assert results[1].event_id == r2.event_id
    assert results[2].event_id == r1.event_id


def test_list_recent_scoped_to_campaign(campaign_conn: sqlite3.Connection) -> None:
    """list_recent returns only the requested campaign's events."""
    other_campaign = "other-camp99"
    # Insert second campaign row
    campaign_conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (other_campaign, "Other Campaign", "other-campaign", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    campaign_conn.commit()

    service = SafetyEventService(conn=campaign_conn)
    service.log_pause(campaign_id=_CAMPAIGN_ID)
    service.log_pause(campaign_id=other_campaign)

    results = service.list_recent(_CAMPAIGN_ID)
    assert len(results) == 1
    assert results[0].campaign_id == _CAMPAIGN_ID


def test_log_atomic_on_canary_hit(campaign_conn: sqlite3.Connection) -> None:
    """Canary hit → DB unchanged (transaction rollback guarantee)."""
    from sagasmith.evals.redaction import RedactionCanary, RedactionHit

    # RedactionCanary is a frozen dataclass — can't patch.object on it.
    # Instead, subclass it to always fire, bypassing the frozen restriction.
    class AlwaysHitsCanary(RedactionCanary):
        def scan(self, text: str) -> list[RedactionHit]:
            return [RedactionHit(label="fake_secret", match="sk-proj-fake", index=0)]

    service = SafetyEventService(conn=campaign_conn, _canary=AlwaysHitsCanary())

    with pytest.raises(TrustServiceError):
        service.log_pause(campaign_id=_CAMPAIGN_ID)

    count = campaign_conn.execute("SELECT COUNT(*) FROM safety_events").fetchone()[0]
    assert count == 0
