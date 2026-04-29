"""Integration tests for transcript-to-memory context flow."""

from __future__ import annotations

import sqlite3

from sagasmith.evals.fixtures import make_valid_saga_state
from sagasmith.graph.bootstrap import GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "turn_prev",
            "cmp_001",
            "sess_001",
            "complete",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:10Z",
            1,
        ),
    )
    conn.execute(
        "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            "turn_prev",
            "narration_final",
            "Marcus pointed toward Rivermouth Market.",
            0,
            "2026-01-01T00:00:00Z",
        ),
    )
    conn.commit()
    return conn


def test_full_flow_makes_memory_packet_available_and_logs_archivist_skill() -> None:
    conn = _make_conn()
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="t", session_seed="s"),
        cost=CostGovernor(session_budget_usd=1.0),
        skill_store=default_skill_store(),
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        session_id="sess_001",
        turn_id="turn_000001",
        phase="play",
        memory_packet=None,
        scene_brief=None,
        pending_player_input="ask Marcus about the market",
    ).model_dump()

    before_orator = runtime.invoke_turn(state)
    assert before_orator["memory_packet"] is not None
    assert "Marcus pointed" in "\n".join(before_orator["memory_packet"]["recent_turns"])

    runtime.resume_and_close(
        TurnRecord(
            turn_id="turn_000001",
            campaign_id="cmp_001",
            session_id="sess_001",
            status="needs_vault_repair",
            started_at="2026-01-01T00:01:00Z",
            completed_at="2026-01-01T00:01:10Z",
            schema_version=1,
        )
    )
    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert any(
        row.agent_name == "archivist" and row.skill_name == "memory-packet-assembly" for row in rows
    )
