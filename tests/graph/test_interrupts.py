"""Tests for graph interrupt primitives.

Covers InterruptKind, InterruptEnvelope, RedactionCanary guard,
GraphRuntime.post_interrupt / resume_after_interrupt, and
BudgetStopError → BUDGET_STOP translation at the runtime boundary.
"""

from __future__ import annotations

import sqlite3
from typing import Any, cast

import pytest

from sagasmith.graph.bootstrap import GraphBootstrap
from sagasmith.graph.interrupts import (
    InterruptEnvelope,
    InterruptKind,
    extract_pending_interrupt,
)
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.services.errors import BudgetStopError, TrustServiceError


def _make_conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:", check_same_thread=False)


def _insert_campaign_and_turn(conn: sqlite3.Connection, *, status: str = "complete") -> None:
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "turn_000001",
            "cmp_001",
            "sess_001",
            status,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            1,
        ),
    )
    conn.commit()


def _make_bootstrap():
    dice = DiceService(campaign_seed="x", session_seed="y")
    cost = CostGovernor(session_budget_usd=1.0)
    return GraphBootstrap.from_services(dice=dice, cost=cost)


def _play_state():
    return {
        "campaign_id": "cmp_001",
        "session_id": "sess_001",
        "turn_id": "turn_000001",
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
    }


# ---------------------------------------------------------------------------
# Test 1: InterruptKind enum values
# ---------------------------------------------------------------------------


def test_interrupt_kind_values():
    assert InterruptKind.PAUSE == "pause"
    assert InterruptKind.LINE == "line"
    assert InterruptKind.RETCON == "retcon"
    assert InterruptKind.BUDGET_STOP == "budget_stop"
    assert InterruptKind.SESSION_END == "session_end"


# ---------------------------------------------------------------------------
# Test 2: InterruptEnvelope round-trip serialization
# ---------------------------------------------------------------------------


def test_interrupt_envelope_round_trip():
    envelope = InterruptEnvelope.build(
        kind=InterruptKind.PAUSE,
        payload={"reason": "test"},
        thread_id="campaign:c1",
    )
    dumped = envelope.model_dump()
    assert dumped["kind"] == "pause"
    assert dumped["payload"] == {"reason": "test"}
    assert dumped["thread_id"] == "campaign:c1"
    assert "created_at" in dumped


# ---------------------------------------------------------------------------
# Test 3: RedactionCanary rejects secret-shaped payload
# ---------------------------------------------------------------------------


def test_envelope_rejects_secret_shaped_payload():
    with pytest.raises(TrustServiceError):
        InterruptEnvelope.build(
            kind=InterruptKind.PAUSE,
            payload={"secret": "sk-proj-supersecretkeyblablabla"},
            thread_id="campaign:c1",
        )


# ---------------------------------------------------------------------------
# Test 4: GraphRuntime.post_interrupt records envelope in state
# ---------------------------------------------------------------------------


def test_post_interrupt_records_in_graph_state():
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    envelope = runtime.post_interrupt(kind=InterruptKind.PAUSE, payload={"reason": "test"})
    assert envelope.kind == InterruptKind.PAUSE

    snapshot = runtime.graph.get_state(runtime.thread_config)
    assert snapshot.values["last_interrupt"]["kind"] == "pause"
    assert snapshot.values["last_interrupt"]["payload"] == {"reason": "test"}


# ---------------------------------------------------------------------------
# Test 5: GraphRuntime.resume_after_interrupt clears and resumes
# ---------------------------------------------------------------------------


def test_resume_after_interrupt_clears_and_resumes():
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    runtime.post_interrupt(kind=InterruptKind.PAUSE, payload={"reason": "test"})
    assert extract_pending_interrupt(runtime) is not None

    # Run a turn first so there's state to resume from
    state = _play_state()
    runtime.invoke_turn(state)

    runtime.resume_after_interrupt()
    assert extract_pending_interrupt(runtime) is None


# ---------------------------------------------------------------------------
# Test 6: extract_pending_interrupt helper
# ---------------------------------------------------------------------------


def test_extract_pending_interrupt_returns_envelope_or_none():
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    assert extract_pending_interrupt(runtime) is None
    runtime.post_interrupt(kind=InterruptKind.LINE, payload={"topic": "x"})
    pending = extract_pending_interrupt(runtime)
    assert pending is not None
    assert pending["kind"] == "line"


# ---------------------------------------------------------------------------
# Test 7: BudgetStopError → BUDGET_STOP interrupt translation
# ---------------------------------------------------------------------------


def test_invoke_turn_translates_budget_stop_error():
    """Simulate a node raising BudgetStopError; runtime translates to interrupt."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)

    # Build a bootstrap whose oracle node raises BudgetStopError
    dice = DiceService(campaign_seed="x", session_seed="y")
    cost = CostGovernor(session_budget_usd=1.0)
    bootstrap = GraphBootstrap.from_services(dice=dice, cost=cost)

    original_oracle = bootstrap.oracle

    def raising_oracle(state, **kwargs):
        raise BudgetStopError("budget exhausted")

    # Patch oracle on the bootstrap directly
    from dataclasses import replace

    patched = replace(bootstrap, oracle=raising_oracle)

    runtime = build_persistent_graph(patched, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)

    # The interrupt should be in state
    pending = extract_pending_interrupt(runtime)
    assert pending is not None
    assert pending["kind"] == "budget_stop"
    assert "budget exhausted" in pending["payload"]["reason"]

    # Verify the original oracle node code does NOT reference BudgetStopError
    import inspect

    oracle_obj = cast(Any, original_oracle)
    oracle_source = inspect.getsource(
        oracle_obj.func if hasattr(oracle_obj, "func") else oracle_obj
    )
    assert "BudgetStopError" not in oracle_source
    assert "InterruptKind" not in oracle_source


# ---------------------------------------------------------------------------
# Test 8: Single-slot overwrite semantics
# ---------------------------------------------------------------------------


def test_post_interrupt_overwrites_single_slot():
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    runtime.post_interrupt(kind=InterruptKind.PAUSE, payload={"reason": "first"})
    runtime.post_interrupt(kind=InterruptKind.LINE, payload={"topic": "second"})

    pending = extract_pending_interrupt(runtime)
    assert pending is not None
    assert pending["kind"] == "line"
    assert pending["payload"]["topic"] == "second"


# ---------------------------------------------------------------------------
# Test 9: Session-end round-trip
# ---------------------------------------------------------------------------


def test_session_end_interrupt_round_trip():
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    runtime.post_interrupt(kind=InterruptKind.SESSION_END, payload={"reason": "player quit"})
    pending = extract_pending_interrupt(runtime)
    assert pending is not None
    assert pending["kind"] == "session_end"

    runtime.resume_after_interrupt()
    assert extract_pending_interrupt(runtime) is None
