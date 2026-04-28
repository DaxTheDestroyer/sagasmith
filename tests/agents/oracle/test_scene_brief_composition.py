"""Tests for Oracle scene brief composition."""

from __future__ import annotations

import pytest

from sagasmith.agents.oracle.skills.scene_brief_composition.logic import compose_scene_brief
from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_content_policy,
    make_valid_memory_packet,
    make_valid_player_profile,
    make_valid_scene_brief,
)
from sagasmith.providers import DeterministicFakeClient
from sagasmith.schemas.narrative import SceneBrief
from sagasmith.services.cost import CostGovernor


def test_scene_brief_model_accepts_parallel_beat_ids() -> None:
    brief = make_valid_scene_brief()

    assert brief.beat_ids == ["beat_riverbank_clues", "beat_choose_approach"]
    assert SceneBrief.model_validate(brief.model_dump()) == brief


def test_scene_brief_rejects_player_facing_narration() -> None:
    data = make_valid_scene_brief().model_dump()
    data["beats"][0] = "You see footprints by the river."

    with pytest.raises(ValueError, match="planning-only"):
        SceneBrief.model_validate(data)


def test_compose_scene_brief_uses_structured_fake_client_and_context() -> None:
    payload = make_valid_scene_brief(
        intent="Plan a quiet clue scene.",
        content_warnings=["graphic_violence:fade_to_black"],
    ).model_dump()
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.scene-brief-composition": make_fake_llm_response(parsed_json=payload)
        }
    )
    logs = []

    brief = compose_scene_brief(
        player_input="search the riverbank",
        memory_packet=make_valid_memory_packet(),
        content_policy=make_valid_content_policy(),
        player_profile=make_valid_player_profile(),
        llm_client=client,
        scene_intent="Plan a quiet clue scene.",
        cost_governor=CostGovernor(session_budget_usd=1.0),
        logger=logs.append,
        turn_id="turn_000001",
    )

    assert brief.intent == "Plan a quiet clue scene."
    assert brief.beat_ids
    assert logs and logs[0].agent_name == "oracle"
