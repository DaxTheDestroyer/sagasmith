"""Integration coverage for natural-language RulesLawyer intent flow."""

from __future__ import annotations

import sqlite3

from sagasmith.agents.rules_lawyer.node import rules_lawyer_node
from sagasmith.evals.fixtures import make_fake_llm_response, make_valid_saga_state
from sagasmith.graph.bootstrap import GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.providers import DeterministicFakeClient
from sagasmith.rules.first_slice import make_first_slice_character
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


def _state(player_input: str) -> dict[str, object]:
    return make_valid_saga_state(
        pending_player_input=player_input,
        character_sheet=make_first_slice_character(),
        check_results=[],
        pending_narration=[],
        combat_state=None,
    ).model_dump()


def test_natural_language_skill_action_resolves_without_paid_call() -> None:
    services = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="intent", session_seed="flow"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=None,
        skill_store=default_skill_store(),
    ).services

    result = rules_lawyer_node(_state("I climb the slick cliff"), services)

    assert result["check_results"][0]["proposal_id"].startswith("check_athletics_")
    assert result["pending_narration"] if "pending_narration" in result else True


def test_mixed_narrative_input_skips_mechanics() -> None:
    services = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="intent", session_seed="flow"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=None,
        skill_store=default_skill_store(),
    ).services

    assert rules_lawyer_node(_state("I tell the child a quiet story"), services) == {}


def test_llm_fallback_flow_resolves_and_logs_skill_activation() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("turn_000001", "cmp_001", "sess_001", "complete", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 1),
    )
    conn.commit()
    client = DeterministicFakeClient(
        {
            "rules_lawyer.intent-resolution": make_fake_llm_response(
                parsed_json={
                    "candidates": [
                        {
                            "action": "skill_check",
                            "stat": "survival",
                            "target_id": None,
                            "attack_id": None,
                            "position": None,
                            "confidence": 0.88,
                            "reason": "follows signs through the wild",
                        }
                    ]
                }
            )
        }
    )
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="intent", session_seed="flow"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=client,
        skill_store=default_skill_store(),
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
    state = _state("I read the snapped branches for direction")
    state.update({"campaign_id": "cmp_001", "session_id": "sess_001", "turn_id": "turn_000001", "phase": "combat"})

    result = runtime.invoke_turn(state)

    assert result["check_results"][0]["proposal_id"].startswith("check_survival_")
    rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
    assert [row.skill_name for row in rows if row.agent_name == "rules_lawyer"] == [
        "skill-check-resolution"
    ]
