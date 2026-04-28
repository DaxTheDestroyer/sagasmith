"""Tests for compiled graph and bootstrap behavior."""

from __future__ import annotations

import pytest

from sagasmith.evals.fixtures import (
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_player_profile,
    make_valid_saga_state,
)
from sagasmith.graph import GraphBootstrap, build_default_graph
from sagasmith.graph.state import from_saga_state
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


@pytest.fixture
def services():
    return GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="test", session_seed="s1"),
        cost=CostGovernor(session_budget_usd=1.0),
        safety=None,
        llm=None,
        _call_recorder=[],
    )


class TestGraphBootstrap:
    def test_from_services_constructs(self, services) -> None:
        """Test 1: GraphBootstrap.from_services constructs without raising."""
        assert services.services.dice is not None
        assert services.services.cost is not None

    def test_build_default_graph_returns_compiled_graph(self, services) -> None:
        """Test 1b: build_default_graph returns a compiled StateGraph."""
        graph = build_default_graph(services)
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "stream")
        assert hasattr(graph, "get_graph")

    def test_play_phase_walks_full_chain(self, services) -> None:
        """Test 2: phase=play walks oracle → rules_lawyer → orator → archivist."""
        state = make_valid_saga_state(
            phase="play",
            player_profile=make_valid_player_profile(),
            content_policy=make_valid_content_policy(),
            house_rules=make_valid_house_rules(),
            scene_brief=None,
            pending_player_input=None,
            pending_narration=[],
            check_results=[],
        )
        graph = build_default_graph(services)
        graph.invoke(from_saga_state(state), {"configurable": {"thread_id": "t1"}})
        assert services.services._call_recorder == [
            "oracle",
            "rules_lawyer",
            "orator",
            "archivist",
        ]

    def test_paused_terminates_immediately(self, services) -> None:
        """Test 3: phase=paused terminates immediately."""
        state = make_valid_saga_state(phase="paused")
        graph = build_default_graph(services)
        graph.invoke(from_saga_state(state), {"configurable": {"thread_id": "t2"}})
        assert services.services._call_recorder == []

    def test_session_end_terminates_immediately(self, services) -> None:
        """Test 4: phase=session_end terminates immediately."""
        state = make_valid_saga_state(phase="session_end")
        graph = build_default_graph(services)
        graph.invoke(from_saga_state(state), {"configurable": {"thread_id": "t3"}})
        assert services.services._call_recorder == []

    def test_combat_routes_through_rules_lawyer_chain(self, services) -> None:
        """Test 5: phase=combat enters RulesLawyer first-slice mechanics."""
        state = make_valid_saga_state(phase="combat")
        graph = build_default_graph(services)
        graph.invoke(from_saga_state(state), {"configurable": {"thread_id": "t4"}})
        assert services.services._call_recorder == ["rules_lawyer", "orator", "archivist"]

    def test_bootstrap_tolerates_llm_none(self) -> None:
        """Test 13: Bootstrap tolerates llm=None."""
        services = GraphBootstrap.from_services(
            dice=DiceService(campaign_seed="test", session_seed="s1"),
            cost=CostGovernor(session_budget_usd=1.0),
            llm=None,
        )
        assert services.services.llm is None
        graph = build_default_graph(services)
        assert hasattr(graph, "invoke")
