"""Tests for Oracle campaign seed generation."""

from __future__ import annotations

import pytest

from sagasmith.agents.oracle.skills.campaign_seed_generation.logic import generate_campaign_seed
from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_campaign_seed,
    make_valid_player_profile,
    make_valid_world_bible,
)
from sagasmith.providers import DeterministicFakeClient
from sagasmith.schemas.campaign_seed import CampaignSeed
from sagasmith.services.cost import CostGovernor


def test_campaign_seed_model_validates_three_to_five_hooks() -> None:
    seed = make_valid_campaign_seed()

    assert len(seed.plot_hooks) == 3
    assert CampaignSeed.model_validate(seed.model_dump()) == seed


def test_campaign_seed_rejects_selected_arc_without_matching_hook() -> None:
    data = make_valid_campaign_seed().model_dump()
    data["selected_arc"]["selected_hook_id"] = "missing"

    with pytest.raises(ValueError, match=r"selected_arc\.selected_hook_id"):
        CampaignSeed.model_validate(data)


def test_generate_campaign_seed_returns_distinct_aligned_hooks() -> None:
    payload = make_valid_campaign_seed().model_dump()
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.campaign-seed-generation": make_fake_llm_response(parsed_json=payload)
        }
    )
    logs = []

    seed = generate_campaign_seed(
        world_bible=make_valid_world_bible(),
        player_profile=make_valid_player_profile(),
        llm_client=client,
        cost_governor=CostGovernor(session_budget_usd=1.0),
        logger=logs.append,
        turn_id="turn_000001",
    )

    assert {hook.id for hook in seed.plot_hooks} == {
        "hook_missing_barge",
        "hook_waystone_song",
        "hook_guild_debt",
    }
    assert seed.selected_arc.selected_hook_id == "hook_missing_barge"
    assert logs and logs[0].agent_name == "oracle"
