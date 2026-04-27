"""Tests for sagasmith.onboarding.store — OnboardingStore SQLite persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from sagasmith.onboarding.store import OnboardingStore, OnboardingTriple
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.player import HouseRules
from sagasmith.services.errors import TrustServiceError

from .fixtures import make_happy_path_answers

# ---------------------------------------------------------------------------
# Fixed test campaign ID
# ---------------------------------------------------------------------------

_CAMPAIGN_ID = "test-aaaa1234"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_triple() -> OnboardingTriple:
    """Build a valid OnboardingTriple from happy-path answers."""
    from sagasmith.onboarding.wizard import OnboardingWizard

    wizard = OnboardingWizard()
    for answer_dict in make_happy_path_answers():
        wizard.step(answer_dict)
    profile, policy, rules = wizard.build_records()
    return OnboardingTriple(
        player_profile=profile,
        content_policy=policy,
        house_rules=rules,
    )


@pytest.fixture
def fresh_campaign_conn() -> Generator[sqlite3.Connection, None, None]:
    """In-memory SQLite DB with all migrations applied and one campaigns row."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)

    # Insert a test campaign row
    conn.execute(
        """
        INSERT INTO campaigns (
            campaign_id, campaign_name, campaign_slug,
            created_at, sagasmith_version, manifest_version
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            _CAMPAIGN_ID,
            "Test Campaign",
            "test-campaign",
            "2026-01-01T00:00:00Z",
            "0.1.0",
            1,
        ),
    )
    conn.commit()

    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_commit_writes_all_three_rows(fresh_campaign_conn: sqlite3.Connection) -> None:
    """commit() writes one row to each of the three onboarding tables."""
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    store.commit(_CAMPAIGN_ID, triple)

    # Verify all three rows exist
    profile_row = fresh_campaign_conn.execute(
        "SELECT profile_json FROM onboarding_player_profile WHERE campaign_id = ?",
        (_CAMPAIGN_ID,),
    ).fetchone()
    policy_row = fresh_campaign_conn.execute(
        "SELECT policy_json FROM onboarding_content_policy WHERE campaign_id = ?",
        (_CAMPAIGN_ID,),
    ).fetchone()
    rules_row = fresh_campaign_conn.execute(
        "SELECT rules_json FROM onboarding_house_rules WHERE campaign_id = ?",
        (_CAMPAIGN_ID,),
    ).fetchone()

    assert profile_row is not None
    assert policy_row is not None
    assert rules_row is not None

    # Spot-check that rules_json deserializes back to a valid HouseRules
    rules = HouseRules.model_validate_json(rules_row[0])
    assert rules.session_end_trigger == "player_command_or_budget"


def test_reload_returns_triple_after_commit(fresh_campaign_conn: sqlite3.Connection) -> None:
    """reload() returns the same triple that was committed."""
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    store.commit(_CAMPAIGN_ID, triple)
    loaded = store.reload(_CAMPAIGN_ID)

    assert loaded is not None
    assert loaded.player_profile == triple.player_profile
    assert loaded.content_policy == triple.content_policy
    assert loaded.house_rules == triple.house_rules


def test_reload_returns_none_on_fresh_campaign(fresh_campaign_conn: sqlite3.Connection) -> None:
    """reload() returns None when no onboarding rows exist yet."""
    store = OnboardingStore(fresh_campaign_conn)
    result = store.reload(_CAMPAIGN_ID)
    assert result is None


def test_reload_raises_on_partial_state(fresh_campaign_conn: sqlite3.Connection) -> None:
    """reload() raises TrustServiceError when only some tables have a row."""
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    # Manually insert only the player_profile row (simulating interrupted commit)
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    fresh_campaign_conn.execute(
        "INSERT INTO onboarding_player_profile (campaign_id, profile_json, committed_at) "
        "VALUES (?, ?, ?)",
        (_CAMPAIGN_ID, triple.player_profile.model_dump_json(), now),
    )
    fresh_campaign_conn.commit()

    with pytest.raises(TrustServiceError) as exc_info:
        store.reload(_CAMPAIGN_ID)

    # Error message should mention the missing tables
    error_msg = str(exc_info.value)
    assert "content_policy" in error_msg or "onboarding_content_policy" in error_msg
    assert "house_rules" in error_msg or "onboarding_house_rules" in error_msg


def test_commit_is_atomic_on_validation_failure(fresh_campaign_conn: sqlite3.Connection) -> None:
    """If serialization of the second model fails, no rows should be written.

    Builds a BrokenContentPolicy subclass whose model_dump_json always raises,
    then confirms the sqlite3 ``with conn:`` transaction context rolls back the
    first INSERT when the second raises, leaving all three tables empty.
    """
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    from sagasmith.schemas.player import ContentPolicy as _ContentPolicy

    class BrokenContentPolicy(_ContentPolicy):
        """ContentPolicy subclass whose serialization always raises."""

        def model_dump_json(self, **kwargs: object) -> str:  # type: ignore[override]
            raise RuntimeError("simulated serialization failure on content_policy")

    # Build the broken object BEFORE any patching
    broken_policy = BrokenContentPolicy.model_construct(
        hard_limits=["test"],
        soft_limits={},
        preferences=[],
    )
    broken_triple = OnboardingTriple(
        player_profile=triple.player_profile,
        content_policy=broken_policy,  # type: ignore[arg-type]
        house_rules=triple.house_rules,
    )

    with pytest.raises(RuntimeError, match="simulated serialization failure"):
        store.commit(_CAMPAIGN_ID, broken_triple)

    # After the failed commit, no rows should be present (transaction rolled back)
    profile_count = fresh_campaign_conn.execute(
        "SELECT COUNT(*) FROM onboarding_player_profile WHERE campaign_id = ?",
        (_CAMPAIGN_ID,),
    ).fetchone()[0]
    assert profile_count == 0, "Profile row should not survive a failed atomic commit"


def test_commit_twice_overwrites(fresh_campaign_conn: sqlite3.Connection) -> None:
    """Committing twice with different triples succeeds and returns the latest (ONBD-05)."""
    store = OnboardingStore(fresh_campaign_conn)
    triple_a = _make_triple()

    store.commit(_CAMPAIGN_ID, triple_a)

    # Build a second triple with a different pacing
    from sagasmith.onboarding.wizard import OnboardingWizard

    from .fixtures import make_happy_path_answers

    answers_b = make_happy_path_answers()
    answers_b[2] = dict(answers_b[2])  # type: ignore[assignment]
    answers_b[2]["pacing"] = "slow"  # type: ignore[index]

    wizard_b = OnboardingWizard()
    for answer_dict in answers_b:
        wizard_b.step(answer_dict)
    profile_b, policy_b, rules_b = wizard_b.build_records()
    triple_b = OnboardingTriple(
        player_profile=profile_b,
        content_policy=policy_b,
        house_rules=rules_b,
    )

    # Second commit should not raise UNIQUE constraint
    store.commit(_CAMPAIGN_ID, triple_b)

    loaded = store.reload(_CAMPAIGN_ID)
    assert loaded is not None
    assert loaded.player_profile.pacing == "slow"


def test_commit_requires_campaign_fk(fresh_campaign_conn: sqlite3.Connection) -> None:
    """commit() raises IntegrityError when campaign_id doesn't exist in campaigns table."""
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    with pytest.raises(sqlite3.IntegrityError):
        store.commit("not-a-real-id", triple)


def test_exists_matches_reload_state(fresh_campaign_conn: sqlite3.Connection) -> None:
    """exists() returns False before commit and True after commit."""
    store = OnboardingStore(fresh_campaign_conn)
    triple = _make_triple()

    assert store.exists(_CAMPAIGN_ID) is False

    store.commit(_CAMPAIGN_ID, triple)

    assert store.exists(_CAMPAIGN_ID) is True


def test_migration_0003_creates_three_tables(fresh_campaign_conn: sqlite3.Connection) -> None:
    """Migration 0003 creates onboarding_player_profile, _content_policy, _house_rules."""
    tables = {
        row[0]
        for row in fresh_campaign_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "onboarding_player_profile" in tables
    assert "onboarding_content_policy" in tables
    assert "onboarding_house_rules" in tables


def test_migration_schema_version_reaches_3(fresh_campaign_conn: sqlite3.Connection) -> None:
    """After all migrations, schema_version should be at least 3."""
    from sagasmith.persistence.migrations import current_schema_version
    version = current_schema_version(fresh_campaign_conn)
    assert version >= 3
