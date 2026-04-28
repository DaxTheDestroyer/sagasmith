"""Snapshot-style tests for Oracle world generation prompt modules."""

from __future__ import annotations

from sagasmith.evals.fixtures import (
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_player_profile,
    make_valid_world_bible,
)
from sagasmith.prompts.oracle import campaign_seed_generation, world_bible_generation


def test_world_bible_prompt_contains_version_and_onboarding_context() -> None:
    rendered = world_bible_generation.build_user_prompt(
        make_valid_player_profile(), make_valid_content_policy(), make_valid_house_rules()
    )

    assert "PROMPT_VERSION=2026-04-28-1" in world_bible_generation.SYSTEM_PROMPT
    assert '"genre": [' in rendered
    assert "graphic_sexual_content" in rendered
    assert "WorldBible" in str(world_bible_generation.JSON_SCHEMA)


def test_campaign_seed_prompt_contains_version_and_world_context() -> None:
    rendered = campaign_seed_generation.build_user_prompt(
        make_valid_world_bible(), make_valid_player_profile()
    )

    assert "PROMPT_VERSION=2026-04-28-1" in campaign_seed_generation.SYSTEM_PROMPT
    assert "Hopeful frontier mystery" in rendered
    assert "Create 3-5 distinct opening plot hooks" in rendered
    assert "CampaignSeed" in str(campaign_seed_generation.JSON_SCHEMA)
