"""Tests for AgentActivationLogger and contextvar handoff."""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.evals.redaction import RedactionCanary, RedactionHit
from sagasmith.graph.activation_log import (
    AgentActivationLogger,
    get_current_activation,
)
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.services.errors import TrustServiceError


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _insert_turn_record(conn: sqlite3.Connection, turn_id: str) -> None:
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (turn_id, "camp-test", "sess-test", "complete", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 1),
    )
    conn.commit()


def test_activation_logger_writes_success_row() -> None:
    """AgentActivationLogger context manager writes a success row on clean exit."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_001")

    with AgentActivationLogger(conn, turn_id="turn_001", agent_name="oracle"):
        pass

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_001")
    assert len(rows) == 1
    assert rows[0].agent_name == "oracle"
    assert rows[0].outcome == "success"
    assert rows[0].skill_name is None
    assert rows[0].started_at is not None
    assert rows[0].completed_at is not None


def test_activation_logger_writes_error_row_on_exception() -> None:
    """AgentActivationLogger writes an error row and re-raises on exception."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_002")

    with pytest.raises(RuntimeError, match="boom"):
        with AgentActivationLogger(conn, turn_id="turn_002", agent_name="rules_lawyer"):
            raise RuntimeError("boom")

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_002")
    assert len(rows) == 1
    assert rows[0].agent_name == "rules_lawyer"
    assert rows[0].outcome == "error"


def test_activation_logger_set_skill_is_idempotent() -> None:
    """set_skill updates skill_name; final value is persisted."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_003")

    with AgentActivationLogger(conn, turn_id="turn_003", agent_name="orator") as log:
        log.set_skill("narrate-scene")
        log.set_skill("narrate-combat")

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_003")
    assert len(rows) == 1
    assert rows[0].skill_name == "narrate-combat"


def test_activation_logger_set_skill_rejects_invalid_name() -> None:
    """set_skill with invalid name raises ValueError BEFORE write; __exit__ records error."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_004")

    with pytest.raises(ValueError):
        with AgentActivationLogger(conn, turn_id="turn_004", agent_name="archivist") as log:
            log.set_skill("Invalid_Skill")

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_004")
    assert len(rows) == 1
    assert rows[0].outcome == "error"
    assert rows[0].skill_name is None  # invalid skill was never set


def test_activation_logger_redaction_canary_blocks_insert() -> None:
    """RedactionCanary hit before INSERT raises TrustServiceError and writes no row."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_redact")

    class AlwaysFire(RedactionCanary):
        def scan(self, text: str):
            return [RedactionHit(label="test", match="x", index=0)]

    with pytest.raises(TrustServiceError):
        with AgentActivationLogger(
            conn, turn_id="turn_redact", agent_name="oracle", canary=AlwaysFire()
        ):
            pass

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_redact")
    assert len(rows) == 0


def test_activation_logger_rollback_safe() -> None:
    """BEGIN; with AgentActivationLogger; ROLLBACK → no rows remain."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_rollback")

    conn.execute("BEGIN IMMEDIATE")
    with AgentActivationLogger(conn, turn_id="turn_rollback", agent_name="oracle"):
        pass
    conn.rollback()

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_rollback")
    assert len(rows) == 0


def test_get_current_activation_outside_context_is_none() -> None:
    """get_current_activation returns None when no logger is active."""
    assert get_current_activation() is None


def test_get_current_activation_inside_context() -> None:
    """get_current_activation returns the active logger inside a with block."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_ctx")

    with AgentActivationLogger(conn, turn_id="turn_ctx", agent_name="oracle") as log:
        assert get_current_activation() is log

    assert get_current_activation() is None


def test_nested_contextvar_restores_outer() -> None:
    """Nested with blocks correctly restore the outer logger on inner exit."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_nested")
    _insert_turn_record(conn, "turn_nested2")

    with AgentActivationLogger(conn, turn_id="turn_nested", agent_name="oracle") as outer:
        assert get_current_activation() is outer
        with AgentActivationLogger(conn, turn_id="turn_nested2", agent_name="archivist") as inner:
            assert get_current_activation() is inner
        assert get_current_activation() is outer

    assert get_current_activation() is None


def test_langgraph_interrupt_maps_to_interrupted_outcome() -> None:
    """LangGraph Interrupt-like exception maps to outcome='interrupted' and is re-raised."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_interrupt")

    # Simulate a LangGraph interrupt exception class
    GraphInterrupt = type("GraphInterrupt", (Exception,), {"__module__": "langgraph.errors"})

    with pytest.raises(GraphInterrupt):
        with AgentActivationLogger(conn, turn_id="turn_interrupt", agent_name="orator"):
            raise GraphInterrupt("player_input_required")

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_interrupt")
    assert len(rows) == 1
    assert rows[0].agent_name == "orator"
    assert rows[0].outcome == "interrupted"


def test_back_to_back_activations_same_turn() -> None:
    """Two back-to-back activation loggers for different agents on the same turn write two rows."""
    conn = _make_conn()
    apply_migrations(conn)
    _insert_turn_record(conn, "turn_multi")

    with AgentActivationLogger(conn, turn_id="turn_multi", agent_name="oracle"):
        pass

    with AgentActivationLogger(conn, turn_id="turn_multi", agent_name="rules_lawyer"):
        pass

    rows = AgentSkillLogRepository(conn).list_for_turn("turn_multi")
    assert len(rows) == 2
    assert rows[0].agent_name == "oracle"
    assert rows[1].agent_name == "rules_lawyer"
