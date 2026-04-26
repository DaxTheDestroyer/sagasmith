"""Tests for persisted-state validation gate."""

from __future__ import annotations

import pydantic
import pytest

from sagasmith.schemas import SagaState
from sagasmith.schemas.validation import PersistedStateError, validate_persisted_state


def make_budget_policy() -> dict[str, object]:
    return {"per_session_usd": 2.5, "hard_stop": True}


def make_player_profile(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "genre": ["high_fantasy"],
        "tone": ["heroic"],
        "touchstones": ["Earthsea"],
        "pillar_weights": {"combat": 0.3, "exploration": 0.3, "social": 0.3, "puzzle": 0.1},
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


def make_saga_state(**overrides: object) -> SagaState:
    data: dict[str, object] = {
        "campaign_id": "camp_1",
        "session_id": "sess_1",
        "turn_id": "turn_1",
        "phase": "play",
        "player_profile": make_player_profile(),
        "content_policy": {"hard_limits": [], "soft_limits": {}, "preferences": []},
        "house_rules": {
            "dice_ux": "reveal",
            "initiative_visible": True,
            "allow_retcon": True,
            "auto_save_every_turn": True,
            "session_end_trigger": "player_command_or_budget",
        },
        "character_sheet": None,
        "session_state": {
            "current_scene_id": "scene_1",
            "current_location_id": "loc_tavern",
            "active_quest_ids": [],
            "in_game_clock": {"day": 1, "hour": 8, "minute": 0},
            "turn_count": 1,
            "transcript_cursor": "transcript://turn_1",
            "last_checkpoint_id": "checkpoint_1",
        },
        "combat_state": None,
        "pending_player_input": None,
        "memory_packet": None,
        "scene_brief": None,
        "check_results": [],
        "state_deltas": [],
        "pending_conflicts": [],
        "safety_events": [],
        "cost_state": {
            "session_budget_usd": 2.5,
            "spent_usd_estimate": 0.0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "warnings_sent": [],
            "hard_stopped": False,
        },
    }
    data.update(overrides)
    return SagaState(**data)


def test_validate_persisted_state_accepts_valid_dict() -> None:
    original = make_saga_state()
    validated = validate_persisted_state(original.model_dump(mode="json"))
    assert isinstance(validated, SagaState)
    assert validated == original


def test_validate_persisted_state_rejects_missing_required_field() -> None:
    data = make_saga_state().model_dump(mode="json")
    del data["campaign_id"]

    with pytest.raises(PersistedStateError, match="campaign_id"):
        validate_persisted_state(data)


def test_validate_persisted_state_rejects_invalid_enum() -> None:
    data = make_saga_state().model_dump(mode="json")
    data["phase"] = "unknown_phase"

    with pytest.raises(PersistedStateError, match="phase"):
        validate_persisted_state(data)


def test_validate_persisted_state_rejects_violated_model_validator() -> None:
    data = make_saga_state().model_dump(mode="json")
    player_profile = data["player_profile"]
    assert isinstance(player_profile, dict)
    player_profile["pillar_weights"] = {
        "combat": 0.1,
        "exploration": 0.1,
        "social": 0.1,
        "puzzle": 0.1,
    }

    with pytest.raises(PersistedStateError, match="pillar_weights"):
        validate_persisted_state(data)


def test_validate_persisted_state_rejects_non_dict_input() -> None:
    with pytest.raises(PersistedStateError, match="dict"):
        validate_persisted_state("not a dict")


def test_persisted_state_error_is_not_pydantic_error() -> None:
    assert issubclass(PersistedStateError, Exception)
    assert not issubclass(PersistedStateError, pydantic.ValidationError)
