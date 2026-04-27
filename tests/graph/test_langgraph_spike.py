"""LangGraph integration spike.

This test proves the four LangGraph assumptions Plan 04-02 depends on:
1. interrupt_before fires at compile time.
2. get_state().config['configurable']['checkpoint_id'] is accessible after an invoke.
3. None input resumes past the interrupt (Command(resume=None) hits a bug in
   LangGraph 1.1.10 — we use the simpler None-resume pattern instead).
4. SqliteSaver shares a user-provided connection and creates tables that do NOT
   collide with SagaSmith's migration 0001-0004 table names.

If this test ever fails, Plans 04-02 Task 2 onward must be re-designed. Keep
this test as regression coverage for LangGraph version upgrades.
"""

import sqlite3
from typing import TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from sagasmith.persistence.migrations import apply_migrations


class _SpikeState(TypedDict):
    value: int


def _build_spike(conn: sqlite3.Connection):
    g = StateGraph(_SpikeState)
    g.add_node("a", lambda s: {"value": s["value"] + 1})
    g.add_node("b", lambda s: {"value": s["value"] * 10})
    g.add_node("c", lambda s: {"value": s["value"] - 5})
    g.add_edge(START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", END)
    saver = SqliteSaver(conn=conn)
    return g.compile(checkpointer=saver, interrupt_before=["b"])


def _make_conn() -> sqlite3.Connection:
    """Open an in-memory connection that tolerates LangGraph's ThreadPoolExecutor."""
    return sqlite3.connect(":memory:", check_same_thread=False)


def test_interrupt_before_fires():
    conn = _make_conn()
    graph = _build_spike(conn)
    config = {"configurable": {"thread_id": "spike-1"}}
    graph.invoke({"value": 1}, config)
    snapshot = graph.get_state(config)
    assert snapshot.next == ("b",)


def test_checkpoint_id_accessible():
    conn = _make_conn()
    graph = _build_spike(conn)
    config = {"configurable": {"thread_id": "spike-2"}}
    graph.invoke({"value": 1}, config)
    snapshot = graph.get_state(config)
    cp_id = snapshot.config["configurable"].get("checkpoint_id")
    assert cp_id is not None and isinstance(cp_id, str) and len(cp_id) > 0, (
        f"LangGraph snapshot.config missing checkpoint_id: {snapshot.config!r}"
    )


def test_none_resume_advances():
    """Resume with None input (avoids LangGraph 1.1.10 Command(resume=None) bug)."""
    conn = _make_conn()
    graph = _build_spike(conn)
    config = {"configurable": {"thread_id": "spike-3"}}
    graph.invoke({"value": 1}, config)
    graph.invoke(None, config)
    final = graph.get_state(config)
    assert final.next == ()
    assert final.values["value"] == (1 + 1) * 10 - 5


def test_thread_isolation():
    conn = _make_conn()
    graph = _build_spike(conn)
    c1 = {"configurable": {"thread_id": "thread-a"}}
    c2 = {"configurable": {"thread_id": "thread-b"}}
    graph.invoke({"value": 10}, c1)
    graph.invoke({"value": 20}, c2)
    graph.invoke(None, c1)
    graph.invoke(None, c2)
    v1 = graph.get_state(c1).values["value"]
    v2 = graph.get_state(c2).values["value"]
    assert v1 == (10 + 1) * 10 - 5
    assert v2 == (20 + 1) * 10 - 5


SAGASMITH_TABLES = {
    "schema_version",
    "campaigns",
    "settings",
    "turn_records",
    "transcript_entries",
    "roll_logs",
    "provider_logs",
    "state_deltas",
    "cost_logs",
    "checkpoint_refs",
    "safety_events",
    "onboarding_player_profile",
    "onboarding_content_policy",
    "onboarding_house_rules",
}


def test_sqlitesaver_shares_connection_no_collision():
    conn = _make_conn()
    apply_migrations(conn)  # creates all SagaSmith tables through v4
    graph = _build_spike(conn)
    config = {"configurable": {"thread_id": "spike-collide"}}
    graph.invoke({"value": 1}, config)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    sagasmith_present = SAGASMITH_TABLES & tables
    # All SagaSmith tables present:
    missing = SAGASMITH_TABLES - tables
    assert not missing, f"Missing SagaSmith tables after migration+SqliteSaver: {missing}"
    # LangGraph tables present and do NOT overlap with SagaSmith names:
    langgraph_tables = {t for t in tables if t.startswith(("checkpoints", "writes"))}
    assert langgraph_tables, "SqliteSaver created no tables"
    collisions = SAGASMITH_TABLES & langgraph_tables
    assert not collisions, (
        f"LangGraph tables collide with SagaSmith tables: {collisions}. "
        f"This breaks Plan 04-02 Task 2 assumptions. Revisit table naming."
    )
    # Record actual LangGraph table names for the SUMMARY file:
    print(f"LANGGRAPH_TABLES={sorted(langgraph_tables)}")
