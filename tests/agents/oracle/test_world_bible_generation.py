"""Tests for Oracle world bible generation."""

from __future__ import annotations

import pytest

from sagasmith.agents.oracle.skills.world_bible_generation.logic import generate_world_bible
from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_player_profile,
    make_valid_world_bible,
)
from sagasmith.providers import DeterministicFakeClient
from sagasmith.schemas.world import WorldBible
from sagasmith.services.cost import CostGovernor


def test_world_bible_model_validates_required_structure() -> None:
    bible = make_valid_world_bible()

    assert bible.key_locations[0].id == "loc_rivermouth"
    assert WorldBible.model_validate(bible.model_dump()) == bible


def test_world_bible_rejects_duplicate_location_ids() -> None:
    data = make_valid_world_bible().model_dump()
    data["key_locations"][1]["id"] = data["key_locations"][0]["id"]

    with pytest.raises(ValueError, match="key_locations ids must be unique"):
        WorldBible.model_validate(data)


def test_generate_world_bible_uses_structured_fake_client_and_policy_context() -> None:
    payload = make_valid_world_bible(
        safety_notes=["Avoid graphic_sexual_content and harm_to_children."],
    ).model_dump()
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.world-bible-generation": make_fake_llm_response(parsed_json=payload)
        }
    )
    logs = []

    bible = generate_world_bible(
        player_profile=make_valid_player_profile(tone=["hopeful", "mysterious"]),
        content_policy=make_valid_content_policy(),
        house_rules=make_valid_house_rules(),
        llm_client=client,
        cost_governor=CostGovernor(session_budget_usd=1.0),
        logger=logs.append,
        turn_id="turn_000001",
    )

    assert bible.theme == payload["theme"]
    assert any("harm_to_children" in note for note in bible.safety_notes)
    assert logs and logs[0].agent_name == "oracle"
