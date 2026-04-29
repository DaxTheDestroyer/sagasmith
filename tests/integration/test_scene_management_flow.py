"""Integration tests for Oracle scene management flow."""

from __future__ import annotations

import sqlite3

from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_campaign_seed,
    make_valid_saga_state,
    make_valid_scene_brief,
    make_valid_world_bible,
)
from sagasmith.graph.bootstrap import GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.providers import DeterministicFakeClient
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.commit()
    return conn


def test_scene_brief_generation_flow_uses_llm_and_resets_resolved_beats() -> None:
    brief = make_valid_scene_brief(intent="Plan clue discovery at the old ford.")
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.scene-brief-composition": make_fake_llm_response(parsed_json=brief.model_dump())
        }
    )
    conn = _make_conn()
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="t", session_seed="s"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=client,
        skill_store=default_skill_store(),
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        session_id="sess_001",
        turn_id="turn_000001",
        phase="play",
        world_bible=make_valid_world_bible(),
        campaign_seed=make_valid_campaign_seed(),
        scene_brief=None,
        pending_player_input="search the riverbank",
    ).model_dump()

    result = runtime.invoke_turn(state)

    assert result["scene_brief"]["intent"] == "Plan clue discovery at the old ford."
    assert result["scene_brief"]["beat_ids"] == brief.beat_ids
    assert result["resolved_beat_ids"] == []
    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert any(
        row.agent_name == "oracle" and row.skill_name == "scene-brief-composition" for row in rows
    )


def test_scene_routing_skips_oracle_when_beats_unresolved() -> None:
    brief = make_valid_scene_brief()
    conn = _make_conn()
    recorder: list[str] = []
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="t", session_seed="s"),
        cost=CostGovernor(session_budget_usd=1.0),
        skill_store=default_skill_store(),
        _call_recorder=recorder,
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        session_id="sess_001",
        turn_id="turn_000002",
        phase="play",
        scene_brief=brief,
        resolved_beat_ids=[brief.beat_ids[0]],
        pending_player_input="search the riverbank",
    ).model_dump()

    runtime.invoke_turn(state)

    assert "oracle" not in recorder
    assert recorder == ["rules_lawyer"]


def test_oracle_replans_on_player_bypass() -> None:
    prior = make_valid_scene_brief()
    replanned = make_valid_scene_brief(
        scene_id="scene_market_replan",
        intent="Plan around the player's market detour.",
    )
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.scene-brief-composition": make_fake_llm_response(
                parsed_json=replanned.model_dump()
            )
        }
    )
    conn = _make_conn()
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="t", session_seed="s"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=client,
        skill_store=default_skill_store(),
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        session_id="sess_001",
        turn_id="turn_000003",
        phase="play",
        world_bible=make_valid_world_bible(),
        campaign_seed=make_valid_campaign_seed(),
        scene_brief=prior,
        resolved_beat_ids=[],
        pending_player_input="I ignore the riverbank and leave for the market instead.",
    ).model_dump()

    result = runtime.invoke_turn(state)

    assert result["scene_brief"]["scene_id"] == "scene_market_replan"
    assert result["oracle_bypass_detected"] is False


def test_content_policy_block_posts_safety_interrupt_before_orator() -> None:
    conn = _make_conn()
    recorder: list[str] = []
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="t", session_seed="s"),
        cost=CostGovernor(session_budget_usd=1.0),
        skill_store=default_skill_store(),
        _call_recorder=recorder,
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        session_id="sess_001",
        turn_id="turn_000004",
        phase="play",
        scene_brief=None,
        pending_player_input="graphic_sexual_content",
    ).model_dump()

    result = runtime.invoke_turn(state)

    assert result["last_interrupt"]["kind"] == "safety_block"
    assert result["scene_brief"] is None
    assert recorder == ["oracle"]
