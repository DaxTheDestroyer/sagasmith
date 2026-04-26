"""Tests for player configuration schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sagasmith.schemas import BudgetPolicy, ContentPolicy, HouseRules, PlayerProfile


def make_budget_policy(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {"per_session_usd": 2.5, "hard_stop": True}
    data.update(overrides)
    return data


def make_player_profile(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "genre": ["high_fantasy"],
        "tone": ["heroic", "hopeful"],
        "touchstones": ["Earthsea"],
        "pillar_weights": {
            "combat": 0.3,
            "exploration": 0.3,
            "social": 0.3,
            "puzzle": 0.1,
        },
        "pacing": "medium",
        "combat_style": "theater_of_mind",
        "dice_ux": "reveal",
        "campaign_length": "open_ended",
        "character_mode": "guided",
        "death_policy": "heroic_recovery",
        "budget": make_budget_policy(),
    }
    data.update(overrides)
    return data


def make_content_policy(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "hard_limits": ["graphic_sexual_content"],
        "soft_limits": {"graphic_violence": "fade_to_black"},
        "preferences": ["moral_ambiguity_ok"],
    }
    data.update(overrides)
    return data


def make_house_rules(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "dice_ux": "reveal",
        "initiative_visible": True,
        "allow_retcon": True,
        "auto_save_every_turn": True,
        "session_end_trigger": "player_command_or_budget",
    }
    data.update(overrides)
    return data


def test_player_profile_rejects_nonmvp_combat_style() -> None:
    with pytest.raises(ValidationError, match="theater_of_mind"):
        PlayerProfile(**make_player_profile(combat_style="grid"))


def test_player_profile_rejects_pillar_weights_not_summing_to_one() -> None:
    with pytest.raises(ValidationError, match=r"sum|1\.0"):
        PlayerProfile(
            **make_player_profile(
                pillar_weights={
                    "combat": 0.3,
                    "exploration": 0.3,
                    "social": 0.3,
                    "puzzle": 0.3,
                }
            )
        )


def test_player_profile_requires_all_four_pillars() -> None:
    with pytest.raises(ValidationError, match="pillar_weights"):
        PlayerProfile(
            **make_player_profile(
                pillar_weights={"combat": 0.4, "exploration": 0.3, "social": 0.3}
            )
        )


def test_player_profile_accepts_valid_minimum() -> None:
    profile = PlayerProfile(**make_player_profile())
    assert PlayerProfile.model_validate(profile.model_dump()) == profile
    assert isinstance(profile.budget, BudgetPolicy)


def test_content_policy_round_trip() -> None:
    policy = ContentPolicy(**make_content_policy())
    assert ContentPolicy.model_validate(policy.model_dump()) == policy


def test_house_rules_session_end_literal() -> None:
    with pytest.raises(ValidationError):
        HouseRules(**make_house_rules(session_end_trigger="player_or_budget"))
