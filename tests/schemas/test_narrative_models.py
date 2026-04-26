"""Tests for narrative schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sagasmith.schemas import GameClock, MemoryPacket, SceneBrief, SessionState


def make_game_clock(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {"day": 1, "hour": 8, "minute": 30}
    data.update(overrides)
    return data


def make_pacing_target(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {"pillar": "social", "tension": "rising", "length": "short"}
    data.update(overrides)
    return data


def make_memory_packet(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "token_cap": 200,
        "summary": "The party reached the tavern.",
        "entities": [
            {
                "entity_id": "npc_marcus_innkeeper",
                "kind": "npc",
                "name": "Marcus",
                "vault_path": "npcs/marcus.md",
                "provisional": False,
            }
        ],
        "recent_turns": ["The innkeeper offered a clue."],
        "open_callbacks": ["cb_missing_merchant"],
        "retrieval_notes": ["Use tavern context."],
    }
    data.update(overrides)
    return data


def test_scene_brief_defaults_empty_callbacks() -> None:
    scene = SceneBrief(
        scene_id="sc1",
        intent="x",
        location=None,
        present_entities=[],
        beats=["b1"],
        success_outs=[],
        failure_outs=[],
        pacing_target=make_pacing_target(),
    )

    assert scene.callbacks_seeded == []
    assert scene.content_warnings == []


def test_memory_packet_enforces_token_cap() -> None:
    with pytest.raises(ValidationError, match="token_cap"):
        MemoryPacket(**make_memory_packet(token_cap=10, summary="x" * 1000))


def test_session_state_cursor_fields_are_strings_or_none() -> None:
    session = SessionState(
        current_scene_id=None,
        current_location_id=None,
        active_quest_ids=[],
        in_game_clock=make_game_clock(),
        turn_count=0,
        transcript_cursor=None,
        last_checkpoint_id=None,
    )

    assert isinstance(session.in_game_clock, GameClock)
    assert session.transcript_cursor is None
    assert session.last_checkpoint_id is None
