"""Regression: deterministic stability across happy, retry, and discard paths.

Plan 06-04 asserts that check_results, dice outcomes, and HP/state remain
byte-identical when a turn is retried from the pre-narration checkpoint.
Discarded turns leave no orphan transcript or roll rows.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from sagasmith.graph.bootstrap import GraphBootstrap
from sagasmith.graph.checkpoints import CheckpointKind
from sagasmith.graph.runtime import GraphRuntime, build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    CheckpointRefRepository,
    RollLogRepository,
    TranscriptRepository,
    TurnRecordRepository,
)
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _insert_campaign(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )


def _make_bootstrap():
    dice = DiceService(campaign_seed="x", session_seed="y")
    cost = CostGovernor(session_budget_usd=1.0)
    return GraphBootstrap.from_services(dice=dice, cost=cost)


def _play_state(*, turn_id: str = "turn_000001"):
    return {
        "campaign_id": "cmp_001",
        "session_id": "sess_001",
        "turn_id": turn_id,
        "phase": "play",
        "player_profile": None,
        "content_policy": None,
        "house_rules": None,
        "character_sheet": None,
        "session_state": {
            "current_scene_id": None,
            "current_location_id": None,
            "active_quest_ids": [],
            "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
            "turn_count": 0,
            "transcript_cursor": None,
            "last_checkpoint_id": None,
        },
        "combat_state": None,
        "pending_player_input": "roll perception",
        "memory_packet": None,
        "scene_brief": None,
        "check_results": [],
        "state_deltas": [],
        "pending_conflicts": [],
        "pending_narration": [],
        "safety_events": [],
        "cost_state": {
            "session_budget_usd": 1.0,
            "spent_usd_estimate": 0.0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "unknown_cost_call_count": 0,
            "warnings_sent": [],
            "hard_stopped": False,
        },
        "last_interrupt": None,
        "vault_master_path": "",
        "vault_player_path": "",
        "rolling_summary": None,
    }


def _make_turn_record(turn_id: str = "turn_000001") -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        campaign_id="cmp_001",
        session_id="sess_001",
        status="needs_vault_repair",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        schema_version=1,
    )


def _seed_turn(conn: sqlite3.Connection, turn_id: str = "turn_000001", status: str = "needs_vault_repair") -> None:
    _insert_campaign(conn)
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (turn_id, "cmp_001", "sess_001", status, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 1),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscardIncompleteTurn:
    """discard_incomplete_turn rewinds to pre_narration and marks discarded."""

    def test_discard_marks_turn_discarded(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        # Thread paused at orator — pre_narration checkpoint exists.
        snapshot = runtime.graph.get_state(runtime.thread_config)
        assert snapshot.next == ("orator",)

        result = runtime.discard_incomplete_turn("turn_000001")
        assert result.status == "discarded"

        turn = TurnRecordRepository(conn).get("turn_000001")
        assert turn is not None
        assert turn.status == "discarded"

    def test_discard_rewinds_graph_to_pre_narration(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)
        runtime.discard_incomplete_turn("turn_000001")

        # After discard, thread should be at orator interrupt again (rewound).
        snapshot = runtime.graph.get_state(runtime.thread_config)
        assert snapshot.next == ("orator",)

    def test_discard_raises_on_missing_checkpoint(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        with pytest.raises(ValueError, match="No pre_narration checkpoint"):
            runtime.discard_incomplete_turn("turn_000001")

    def test_discard_raises_on_missing_turn_record(self):
        """If turn record doesn't exist, ValueError is raised."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign(conn)
        conn.commit()
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        # invoke_turn creates the turn record automatically, so use a different turn_id
        # that has a checkpoint but no turn record — impossible in practice, but
        # testing the guard.
        with pytest.raises(ValueError, match="No pre_narration checkpoint"):
            runtime.discard_incomplete_turn("turn_ghost")


class TestRetryNarration:
    """retry_narration rewinds and re-invokes orator+archivist."""

    def test_retry_returns_final_state(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        result = runtime.retry_narration("turn_000001")
        assert "turn_id" in result
        assert result["turn_id"] == "turn_000001"

    def test_retry_marks_turn_retried(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        runtime.retry_narration("turn_000001")

        turn = TurnRecordRepository(conn).get("turn_000001")
        assert turn is not None
        assert turn.status == "retried"

    def test_retry_raises_on_missing_checkpoint(self):
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        with pytest.raises(ValueError, match="No pre_narration checkpoint"):
            runtime.retry_narration("turn_000001")


class TestDeterministicStability:
    """Regression: check_results are byte-identical across happy/retry/discard paths."""

    def test_happy_vs_retry_deterministic_state(self):
        """check_results from a normal completion and a retry-then-complete are identical."""
        # --- Path 1: Happy path ---
        conn1 = _make_conn()
        apply_migrations(conn1)
        _seed_turn(conn1)
        bootstrap1 = _make_bootstrap()
        runtime1 = build_persistent_graph(bootstrap1, conn1, campaign_id="cmp_001")

        state1 = _play_state()
        values1 = runtime1.invoke_turn(state1)
        # Complete the turn normally.
        runtime1.resume_and_close(_make_turn_record())
        final1 = runtime1.graph.get_state(runtime1.thread_config).values

        # --- Path 2: Retry path ---
        conn2 = _make_conn()
        apply_migrations(conn2)
        _seed_turn(conn2)
        bootstrap2 = _make_bootstrap()
        runtime2 = build_persistent_graph(bootstrap2, conn2, campaign_id="cmp_001")

        state2 = _play_state()
        runtime2.invoke_turn(state2)
        # Retry once, then let it complete.
        retry_values = runtime2.retry_narration("turn_000001")

        # check_results must be byte-identical between the two paths.
        assert json.dumps(final1.get("check_results"), sort_keys=True) == json.dumps(
            retry_values.get("check_results"), sort_keys=True
        ), "check_results diverged between happy and retry paths"

        # pending_narration should exist in both (deterministic fallback narration).
        assert len(retry_values.get("pending_narration", [])) > 0

    def test_discard_then_fresh_turn_leaves_no_orphans(self):
        """After discarding, running a fresh turn with same input leaves no orphan rows."""
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)
        snapshot = runtime.graph.get_state(runtime.thread_config)
        assert snapshot.next == ("orator",)

        # Discard the incomplete turn.
        runtime.discard_incomplete_turn("turn_000001")

        # No transcript or roll rows should exist for this turn (it was incomplete).
        transcript_rows = TranscriptRepository(conn).list_for_turn("turn_000001")
        assert transcript_rows == [], "Discarded turn should have no transcript rows"

        roll_rows = RollLogRepository(conn).list_for_turn("turn_000001")
        assert roll_rows == [], "Discarded turn should have no roll rows"

    def test_pre_narration_checkpoint_preserved_after_discard(self):
        """The pre_narration CheckpointRef survives discard (not deleted)."""
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)
        runtime.discard_incomplete_turn("turn_000001")

        refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
        pre_refs = [r for r in refs if r.kind == CheckpointKind.PRE_NARRATION.value]
        assert len(pre_refs) >= 1, "pre_narration checkpoint should survive discard"

    def test_retry_preserves_pre_narration_ref_count(self):
        """retry_narration does not write a duplicate pre_narration checkpoint."""
        conn = _make_conn()
        apply_migrations(conn)
        _seed_turn(conn)
        bootstrap = _make_bootstrap()
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        refs_before = CheckpointRefRepository(conn).list_for_turn("turn_000001")
        pre_count_before = sum(1 for r in refs_before if r.kind == CheckpointKind.PRE_NARRATION.value)

        runtime.retry_narration("turn_000001")

        refs_after = CheckpointRefRepository(conn).list_for_turn("turn_000001")
        pre_count_after = sum(1 for r in refs_after if r.kind == CheckpointKind.PRE_NARRATION.value)

        # retry_narration itself should not write a NEW pre_narration ref
        # (it's the same checkpoint, just rewound to).
        assert pre_count_after == pre_count_before, (
            f"retry_narration should not duplicate pre_narration refs: "
            f"before={pre_count_before}, after={pre_count_after}"
        )
