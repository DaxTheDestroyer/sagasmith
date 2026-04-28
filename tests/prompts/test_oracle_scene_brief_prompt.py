"""Prompt rendering tests for Oracle scene brief composition."""

from __future__ import annotations

from sagasmith.evals.fixtures import (
    make_valid_content_policy,
    make_valid_memory_packet,
    make_valid_player_profile,
    make_valid_scene_brief,
)
from sagasmith.prompts.oracle import scene_brief_composition as prompt


def test_scene_brief_prompt_renders_versioned_schema_and_context() -> None:
    user_prompt = prompt.build_user_prompt(
        player_input="search the riverbank",
        memory_packet=make_valid_memory_packet(),
        content_policy=make_valid_content_policy(),
        player_profile=make_valid_player_profile(),
        world_bible=None,
        campaign_seed=None,
        prior_scene_brief=make_valid_scene_brief(),
        scene_intent="Plan clue discovery.",
    )

    assert prompt.PROMPT_VERSION in prompt.SYSTEM_PROMPT
    assert prompt.JSON_SCHEMA["title"] == "SceneBrief"
    assert '"scene_intent": "Plan clue discovery."' in user_prompt
    assert '"beat_ids"' in user_prompt
    assert "planning artifact" in user_prompt
