"""Tests for compact SagaState references."""

from __future__ import annotations

import json
from typing import get_args

from sagasmith.schemas import SagaState, SessionState


def make_budget_policy() -> dict[str, object]:
    return {"per_session_usd": 2.5, "hard_stop": True}


def make_player_profile() -> dict[str, object]:
    return {
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


def make_content_policy() -> dict[str, object]:
    return {"hard_limits": [], "soft_limits": {}, "preferences": []}


def make_house_rules() -> dict[str, object]:
    return {
        "dice_ux": "reveal",
        "initiative_visible": True,
        "allow_retcon": True,
        "auto_save_every_turn": True,
        "session_end_trigger": "player_command_or_budget",
    }


def make_game_clock() -> dict[str, object]:
    return {"day": 1, "hour": 8, "minute": 0}


def make_session_state(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "current_scene_id": "scene_1",
        "current_location_id": "loc_tavern",
        "active_quest_ids": ["quest_missing_merchant"],
        "in_game_clock": make_game_clock(),
        "turn_count": 1,
        "transcript_cursor": "transcript://session_1#turn_1",
        "last_checkpoint_id": "checkpoint_1",
    }
    data.update(overrides)
    return data


def make_memory_packet(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "token_cap": 100,
        "summary": "x" * 50,
        "entities": [],
        "recent_turns": [],
        "open_callbacks": [],
        "retrieval_notes": [],
    }
    data.update(overrides)
    return data


def make_cost_state() -> dict[str, object]:
    return {
        "session_budget_usd": 2.5,
        "spent_usd_estimate": 0.0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "warnings_sent": [],
        "hard_stopped": False,
    }


def make_saga_state(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "campaign_id": "camp_1",
        "session_id": "sess_1",
        "turn_id": "turn_1",
        "phase": "play",
        "player_profile": make_player_profile(),
        "content_policy": make_content_policy(),
        "house_rules": make_house_rules(),
        "character_sheet": None,
        "session_state": make_session_state(),
        "combat_state": None,
        "pending_player_input": None,
        "memory_packet": make_memory_packet(),
        "scene_brief": None,
        "check_results": [],
        "state_deltas": [],
        "pending_conflicts": [],
        "safety_events": [],
        "cost_state": make_cost_state(),
        "vault_master_path": "/tmp/vault/master",
        "vault_player_path": "/tmp/vault/player",
    }
    data.update(overrides)
    return data


def test_saga_state_has_no_inline_transcript_or_vault_bodies() -> None:
    state = SagaState(**make_saga_state())
    serialized = json.dumps(state.model_dump(mode="json"))
    assert len(serialized.encode("utf-8")) < 20_000

    huge_payload = "x" * (2 * 1024 * 1024)
    assert len(huge_payload) > 2_000_000
    forbidden_fields = {"transcript_body", "full_transcript", "vault_contents", "session_pages"}
    assert forbidden_fields.isdisjoint(SagaState.model_fields)


def test_saga_state_references_are_string_ids_or_cursors() -> None:
    for field_name in [
        "transcript_cursor",
        "last_checkpoint_id",
        "current_scene_id",
        "current_location_id",
    ]:
        annotation = SessionState.model_fields[field_name].annotation
        assert str in get_args(annotation)
        assert type(None) in get_args(annotation)
