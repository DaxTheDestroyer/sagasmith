"""Tests for persistent graph runtime: SqliteSaver, pre-narration/final CheckpointRef
writes owned by GraphRuntime, activation logging, and resume-at-next-prompt.
"""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.graph.bootstrap import GraphBootstrap
from sagasmith.graph.checkpoints import (
    CheckpointKind,
    build_checkpointer,
    extract_checkpoint_id,
)
from sagasmith.graph.runtime import (
    GraphRuntime,
    build_persistent_graph,
    thread_config_for,
)
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    AgentSkillLogRepository,
    CheckpointRefRepository,
    TurnRecordRepository,
)
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


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
        ("turn_000001", "cmp_001", "sess_001", status, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 1),
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
    }


def test_build_checkpointer_returns_sqlitesaver():
    """build_checkpointer(conn) returns a SqliteSaver wrapping the passed connection."""
    conn = _make_conn()
    cp = build_checkpointer(conn)
    assert cp is not None
    from langgraph.checkpoint.sqlite import SqliteSaver
    assert isinstance(cp, SqliteSaver)


def test_build_persistent_graph_returns_graph_runtime():
    """build_persistent_graph compiles a graph with interrupt_before=['orator']."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    assert isinstance(runtime, GraphRuntime)
    assert runtime.campaign_id == "cmp_001"


def test_thread_config():
    """thread_config_for returns the campaign-scoped thread_id convention."""
    cfg = thread_config_for("cmp_001")
    assert cfg == {"configurable": {"thread_id": "campaign:cmp_001"}}


def test_invoke_turn_writes_pre_narration_checkpoint():
    """invoke_turn pauses before orator and writes a pre_narration CheckpointRef."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)

    snapshot = runtime.graph.get_state(runtime.thread_config)
    assert snapshot.next == ("orator",)

    refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
    assert len(refs) == 1
    assert refs[0].kind == CheckpointKind.PRE_NARRATION.value
    assert refs[0].checkpoint_id is not None
    assert len(refs[0].checkpoint_id) > 0


def test_resume_and_close_writes_final_checkpoint_and_completes_turn():
    """resume_and_close runs orator+archivist, writes final CheckpointRef, marks turn complete."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)

    turn_record = TurnRecord(
        turn_id="turn_000001",
        campaign_id="cmp_001",
        session_id="sess_001",
        status="needs_vault_repair",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        schema_version=1,
    )
    completed = runtime.resume_and_close(turn_record)
    assert completed.status == "complete"

    refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
    kinds = {r.kind for r in refs}
    assert CheckpointKind.PRE_NARRATION.value in kinds
    assert CheckpointKind.FINAL.value in kinds

    turn = TurnRecordRepository(conn).get("turn_000001")
    assert turn is not None
    assert turn.status == "complete"


def test_activation_logging_counts():
    """Full play-turn cycle writes exactly 4 agent_skill_log rows with skill_name NULL."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)
    turn_record = TurnRecord(
        turn_id="turn_000001",
        campaign_id="cmp_001",
        session_id="sess_001",
        status="needs_vault_repair",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        schema_version=1,
    )
    runtime.resume_and_close(turn_record)

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert len(rows) == 4
    names = [r.agent_name for r in rows]
    assert names == ["oracle", "rules_lawyer", "orator", "archivist"]
    for r in rows:
        assert r.outcome == "success"
        assert r.skill_name is None


def test_resume_at_next_prompt():
    """After a completed turn, re-invoking the same thread returns immediately."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)
    turn_record = TurnRecord(
        turn_id="turn_000001",
        campaign_id="cmp_001",
        session_id="sess_001",
        status="needs_vault_repair",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        schema_version=1,
    )
    runtime.resume_and_close(turn_record)

    # Re-invoke should return immediately (thread at END)
    runtime.invoke_turn(state)
    snapshot = runtime.graph.get_state(runtime.thread_config)
    assert snapshot.next == ()

    # No new activation rows should have been written
    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert len(rows) == 4


def test_crash_simulation_and_recovery():
    """invoke_turn without resume leaves pre_narration only; resume_and_close completes."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn, status="needs_vault_repair")
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)

    # Turn is still in needs_vault_repair (not yet completed)
    turn = TurnRecordRepository(conn).get("turn_000001")
    assert turn is not None
    assert turn.status == "needs_vault_repair"

    # Only pre_narration ref exists
    refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
    assert len(refs) == 1
    assert refs[0].kind == CheckpointKind.PRE_NARRATION.value

    # Now resume and close
    turn_record = TurnRecord(
        turn_id="turn_000001",
        campaign_id="cmp_001",
        session_id="sess_001",
        status="needs_vault_repair",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        schema_version=1,
    )
    runtime.resume_and_close(turn_record)

    # Turn is now complete
    turn = TurnRecordRepository(conn).get("turn_000001")
    assert turn is not None
    assert turn.status == "complete"

    # Both refs exist
    refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
    kinds = {r.kind for r in refs}
    assert CheckpointKind.PRE_NARRATION.value in kinds
    assert CheckpointKind.FINAL.value in kinds


def test_extract_checkpoint_id():
    """extract_checkpoint_id returns the checkpoint_id from a snapshot config, or None."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_campaign_and_turn(conn)
    bootstrap = _make_bootstrap()
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

    state = _play_state()
    runtime.invoke_turn(state)
    snapshot = runtime.graph.get_state(runtime.thread_config)

    cp_id = extract_checkpoint_id(snapshot)
    assert cp_id is not None
    assert isinstance(cp_id, str)
    assert len(cp_id) > 0

    # Snapshot with no config returns None
    class FakeSnapshot:
        config = {}
    assert extract_checkpoint_id(FakeSnapshot()) is None
