"""Tests for agent node purity and behavioral contracts."""

from __future__ import annotations

import copy

import pytest

from sagasmith.agents.archivist.node import archivist_node
from sagasmith.agents.onboarding.node import onboarding_node
from sagasmith.agents.oracle.node import oracle_node
from sagasmith.agents.orator.node import orator_node
from sagasmith.agents.rules_lawyer.node import rules_lawyer_node
from sagasmith.evals.fixtures import (
    make_valid_character_sheet,
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_player_profile,
    make_valid_saga_state,
    make_valid_session_state,
)
from sagasmith.graph.bootstrap import AgentServices
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


@pytest.fixture
def services():
    return AgentServices(
        dice=DiceService(campaign_seed="test", session_seed="s1"),
        cost=CostGovernor(session_budget_usd=1.0),
        safety=None,
        llm=None,
    )


class TestNodePurity:
    def test_onboarding_node_does_not_mutate_input(self, services) -> None:
        """Test 6: onboarding_node is pure."""
        state = make_valid_saga_state().model_dump()
        before = copy.deepcopy(state)
        onboarding_node(state, services)
        assert before == state

    def test_oracle_node_does_not_mutate_input(self, services) -> None:
        """Test 6: oracle_node is pure."""
        state = make_valid_saga_state().model_dump()
        before = copy.deepcopy(state)
        oracle_node(state, services)
        assert before == state

    def test_rules_lawyer_node_does_not_mutate_input(self, services) -> None:
        """Test 6: rules_lawyer_node is pure."""
        state = make_valid_saga_state(
            pending_player_input="perception dc 10",
        ).model_dump()
        before = copy.deepcopy(state)
        rules_lawyer_node(state, services)
        assert before == state

    def test_orator_node_does_not_mutate_input(self, services) -> None:
        """Test 6: orator_node is pure."""
        state = make_valid_saga_state().model_dump()
        before = copy.deepcopy(state)
        orator_node(state, services)
        assert before == state

    def test_archivist_node_does_not_mutate_input(self, services) -> None:
        """Test 6: archivist_node is pure."""
        state = make_valid_saga_state().model_dump()
        before = copy.deepcopy(state)
        archivist_node(state, services)
        assert before == state


class TestOracleNode:
    def test_populates_scene_brief_when_absent(self, services) -> None:
        """Test 7: oracle_node populates scene_brief stub when absent."""
        state = make_valid_saga_state(scene_brief=None).model_dump()
        result = oracle_node(state, services)
        assert result.get("scene_brief") is not None
        assert result.get("memory_packet") is not None
        assert result.get("pending_narration") is None

    def test_returns_empty_when_scene_brief_present(self, services) -> None:
        from sagasmith.schemas.narrative import SceneBrief

        brief = SceneBrief(
            scene_id="s1",
            intent="test",
            location=None,
            present_entities=[],
            beats=[],
            success_outs=[],
            failure_outs=[],
            pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        )
        state = make_valid_saga_state(scene_brief=brief).model_dump()
        result = oracle_node(state, services)
        assert result.get("memory_packet") is not None
        assert "scene_brief" not in result


class TestRulesLawyerNode:
    def test_roll_perception_appends_check_result(self, services) -> None:
        """Test 8: deterministic first-slice command produces CheckResult via DiceService."""
        state = make_valid_saga_state(
            pending_player_input="perception dc 10",
            character_sheet=make_valid_character_sheet(),
            check_results=[],
        ).model_dump()
        result = rules_lawyer_node(state, services)
        assert "check_results" in result
        assert len(result["check_results"]) == 1
        cr = result["check_results"][0]
        assert cr["proposal_id"].startswith("check_perception_")
        assert cr["degree"] in ("critical_success", "success", "failure", "critical_failure")
        assert cr["roll_result"]["natural"] in range(1, 21)

    def test_no_match_returns_visible_error(self, services) -> None:
        state = make_valid_saga_state(pending_player_input="hello world").model_dump()
        result = rules_lawyer_node(state, services)
        assert result["check_results"] == []
        assert "Rules error:" in result["pending_narration"][0]

    def test_determinism_natural_and_total(self, services) -> None:
        """Test 9: Same inputs → same natural/total (NOT roll_id)."""
        base_state = make_valid_saga_state(
            pending_player_input="perception dc 10",
            character_sheet=make_valid_character_sheet(),
            check_results=[],
        ).model_dump()
        result_a = rules_lawyer_node(copy.deepcopy(base_state), services)
        result_b = rules_lawyer_node(copy.deepcopy(base_state), services)
        rr_a = result_a["check_results"][0]["roll_result"]
        rr_b = result_b["check_results"][0]["roll_result"]
        assert rr_a["natural"] == rr_b["natural"]
        assert rr_a["total"] == rr_b["total"]
        # roll_id may differ (call counters) — do NOT assert identity


class TestOratorNode:
    def test_appends_narration_when_scene_brief_present(self, services) -> None:
        """Test 10: orator_node appends one string to pending_narration."""
        from sagasmith.schemas.narrative import SceneBrief

        brief = SceneBrief(
            scene_id="s1",
            intent="x",
            location=None,
            present_entities=[],
            beats=[],
            success_outs=[],
            failure_outs=[],
            pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        )
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=[],
        ).model_dump()
        result = orator_node(state, services)
        assert result["pending_narration"] == ["You take a moment to assess the scene."]
        assert result["memory_packet"] is not None

    def test_leaves_unchanged_when_scene_brief_none(self, services) -> None:
        state = make_valid_saga_state(
            scene_brief=None,
            pending_narration=[],
        ).model_dump()
        result = orator_node(state, services)
        assert result.get("memory_packet") is not None
        assert "pending_narration" not in result

    def test_preserves_existing_narration(self, services) -> None:
        from sagasmith.schemas.narrative import SceneBrief

        brief = SceneBrief(
            scene_id="s1",
            intent="x",
            location=None,
            present_entities=[],
            beats=[],
            success_outs=[],
            failure_outs=[],
            pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        )
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=["existing line"],
        ).model_dump()
        result = orator_node(state, services)
        assert result["pending_narration"] == [
            "existing line",
            "You take a moment to assess the scene.",
        ]
        assert result["memory_packet"] is not None


class TestArchivistNode:
    def test_increments_turn_count_and_clears_pending(self, services) -> None:
        """Test 11: archivist_node increments turn_count and drains queues."""
        state = make_valid_saga_state(
            session_state=make_valid_session_state(turn_count=3),
            pending_player_input="look around",
            pending_narration=["line one"],
        ).model_dump()
        result = archivist_node(state, services)
        session_state = result["session_state"]
        assert isinstance(session_state, dict)
        assert session_state["turn_count"] == 4
        assert result["pending_player_input"] is None
        assert result["memory_packet"] is not None
        # Phase 4: pending_narration preserved for TUI sync (Phase 7 will clear after persist)
        assert result["pending_narration"] == ["line one"]


class TestOnboardingNode:
    def test_returns_empty_when_profile_complete(self, services) -> None:
        """Test 12: onboarding_node returns {} when all required fields present."""
        state = make_valid_saga_state(
            player_profile=make_valid_player_profile(),
            content_policy=make_valid_content_policy(),
            house_rules=make_valid_house_rules(),
        ).model_dump()
        result = onboarding_node(state, services)
        assert result == {}

    def test_self_loop_when_profile_missing(self, services) -> None:
        """Test 12: onboarding_node returns phase=onboarding when incomplete."""
        state = make_valid_saga_state(
            player_profile=None,
            content_policy=make_valid_content_policy(),
            house_rules=make_valid_house_rules(),
        ).model_dump()
        result = onboarding_node(state, services)
        assert result == {"phase": "onboarding"}
