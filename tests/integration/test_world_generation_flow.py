"""Integration tests for first-play Oracle world generation flow."""

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


def test_first_play_turn_generates_world_and_seed_once_before_scene_brief() -> None:
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.world-bible-generation": make_fake_llm_response(
                parsed_json=make_valid_world_bible().model_dump()
            ),
            "oracle.campaign-seed-generation": make_fake_llm_response(
                parsed_json=make_valid_campaign_seed().model_dump()
            ),
            "oracle.scene-brief-composition": make_fake_llm_response(
                parsed_json=make_valid_scene_brief().model_dump()
            ),
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
        world_bible=None,
        campaign_seed=None,
        scene_brief=None,
        pending_player_input="begin",
    ).model_dump()

    before_orator = runtime.invoke_turn(state)
    second = runtime.invoke_turn(before_orator)

    assert before_orator["world_bible"]["theme"] == "Hopeful frontier mystery"
    assert (
        before_orator["campaign_seed"]["selected_arc"]["selected_hook_id"] == "hook_missing_barge"
    )
    assert before_orator["scene_brief"] is not None
    assert second["world_bible"] == before_orator["world_bible"]
    assert second["campaign_seed"] == before_orator["campaign_seed"]
    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert any(
        row.agent_name == "oracle" and row.skill_name == "campaign-seed-generation" for row in rows
    )
