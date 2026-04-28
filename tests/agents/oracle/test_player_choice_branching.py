"""Tests for Oracle player-choice branching."""

from __future__ import annotations

from sagasmith.agents.oracle.skills.player_choice_branching.logic import analyze_player_choice
from sagasmith.evals.fixtures import make_valid_memory_packet, make_valid_scene_brief


def test_player_choice_detects_bypass_and_replan_intent() -> None:
    decision = analyze_player_choice(
        player_input="I ignore the riverbank and leave for the market instead.",
        prior_scene_brief=make_valid_scene_brief(),
        memory_packet=make_valid_memory_packet(),
    )

    assert decision.bypass_detected is True
    assert decision.kind == "reframe"
    assert decision.revised_intent and "market" in decision.revised_intent


def test_player_choice_continues_when_input_follows_scene() -> None:
    decision = analyze_player_choice(
        player_input="I search the riverbank for clues.",
        prior_scene_brief=make_valid_scene_brief(),
        memory_packet=make_valid_memory_packet(),
    )

    assert decision.bypass_detected is False
    assert decision.kind == "continue"
    assert decision.revised_intent is None
