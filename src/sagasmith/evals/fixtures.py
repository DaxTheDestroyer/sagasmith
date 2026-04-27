"""Canonical offline fixtures for schema, smoke, and regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sagasmith.schemas import (
    AttackProfile,
    BudgetPolicy,
    CharacterSheet,
    ContentPolicy,
    CostState,
    GameClock,
    HouseRules,
    InventoryItem,
    LLMResponse,
    MemoryEntityRef,
    MemoryPacket,
    PlayerProfile,
    ProviderConfig,
    SagaState,
    SessionState,
    TokenUsage,
)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _with_overrides[T: BaseModel](instance: T, overrides: dict[str, Any]) -> T:
    if not overrides:
        return instance
    merged = instance.model_dump()
    merged.update(overrides)
    return type(instance).model_validate(merged)


def make_valid_budget_policy(**overrides: Any) -> BudgetPolicy:
    """Return a deterministic valid per-session budget policy."""

    instance = BudgetPolicy(per_session_usd=2.5, hard_stop=True)
    return _with_overrides(instance, overrides)


def make_valid_player_profile(**overrides: Any) -> PlayerProfile:
    """Return a deterministic valid onboarding player profile."""

    instance = PlayerProfile(
        genre=["high_fantasy"],
        tone=["heroic", "hopeful"],
        touchstones=["Earthsea", "Dragon Age: Origins"],
        pillar_weights={"combat": 0.3, "exploration": 0.3, "social": 0.3, "puzzle": 0.1},
        pacing="medium",
        combat_style="theater_of_mind",
        dice_ux="reveal",
        campaign_length="arc",
        character_mode="pregenerated",
        death_policy="heroic_recovery",
        budget=make_valid_budget_policy(),
    )
    return _with_overrides(instance, overrides)


def make_valid_content_policy(**overrides: Any) -> ContentPolicy:
    """Return a deterministic valid player content policy."""

    instance = ContentPolicy(
        hard_limits=["graphic_sexual_content", "harm_to_children"],
        soft_limits={"graphic_violence": "fade_to_black"},
        preferences=["moral_ambiguity_ok", "hopeful_endings_preferred"],
    )
    return _with_overrides(instance, overrides)


def make_valid_house_rules(**overrides: Any) -> HouseRules:
    """Return deterministic valid MVP house rules."""

    instance = HouseRules(
        dice_ux="reveal",
        initiative_visible=True,
        allow_retcon=True,
        auto_save_every_turn=True,
        session_end_trigger="player_command_or_budget",
    )
    return _with_overrides(instance, overrides)


def make_valid_session_state(**overrides: Any) -> SessionState:
    """Return compact deterministic session cursor state."""

    instance = SessionState(
        current_scene_id=None,
        current_location_id=None,
        active_quest_ids=[],
        in_game_clock=GameClock(day=1, hour=9, minute=0),
        turn_count=0,
        transcript_cursor=None,
        last_checkpoint_id=None,
    )
    return _with_overrides(instance, overrides)


def make_valid_cost_state(**overrides: Any) -> CostState:
    """Return deterministic zero-spend cost state."""

    instance = CostState(
        session_budget_usd=2.5,
        spent_usd_estimate=0.0,
        tokens_prompt=0,
        tokens_completion=0,
        warnings_sent=[],
        hard_stopped=False,
    )
    return _with_overrides(instance, overrides)


def make_valid_memory_packet(**overrides: Any) -> MemoryPacket:
    """Return a compact memory packet that references entities by ID/path."""

    instance = MemoryPacket(
        token_cap=256,
        summary="Campaign begins at the Bent Copper Tavern.",
        entities=[
            MemoryEntityRef(
                entity_id="npc_marcus_innkeeper",
                kind="npc",
                name="Marcus",
                vault_path="npcs/npc_marcus_innkeeper.md",
                provisional=False,
            )
        ],
        recent_turns=["turn_0000: The player arrived in Rivermouth."],
        open_callbacks=["cb_missing_merchant_witness"],
        retrieval_notes=["Fixture memory uses IDs and summaries only."],
    )
    return _with_overrides(instance, overrides)


def make_valid_character_sheet(**overrides: Any) -> CharacterSheet:
    """Return a deterministic level-1 martial character sheet."""

    instance = CharacterSheet(
        id="pc-test-hero",
        name="Aric Vale",
        level=1,
        ancestry="Human",
        background="Scout",
        class_name="Fighter",
        abilities={"str": 18, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
        proficiencies={
            "perception": "trained",
            "fortitude": "expert",
            "reflex": "trained",
            "will": "trained",
        },
        max_hp=20,
        current_hp=20,
        armor_class=18,
        perception_modifier=5,
        saving_throws={"fortitude": 7, "reflex": 5, "will": 4},
        skills={"athletics": 7, "survival": 4, "diplomacy": 3, "stealth": 4},
        attacks=[
            AttackProfile(
                id="atk-longsword",
                name="Longsword",
                modifier=9,
                damage="1d8+4 slashing",
                traits=["versatile_p"],
                range=None,
            )
        ],
        inventory=[
            InventoryItem(
                id="item-adventurers-pack", name="Adventurer's Pack", quantity=1, bulk=1.0
            )
        ],
        conditions=[],
    )
    return _with_overrides(instance, overrides)


def make_valid_saga_state(**overrides: Any) -> SagaState:
    """Return the canonical deterministic SagaState fixture instance."""

    instance = SagaState(
        campaign_id="camp-test-0001",
        session_id="sess-test-0001",
        turn_id="turn-0000",
        phase="onboarding",
        player_profile=make_valid_player_profile(),
        content_policy=make_valid_content_policy(),
        house_rules=make_valid_house_rules(),
        character_sheet=make_valid_character_sheet(),
        session_state=make_valid_session_state(),
        combat_state=None,
        pending_player_input=None,
        memory_packet=None,
        scene_brief=None,
        check_results=[],
        state_deltas=[],
        pending_conflicts=[],
        safety_events=[],
        cost_state=make_valid_cost_state(),
    )
    return _with_overrides(instance, overrides)


def make_fake_provider_config(**overrides: Any) -> ProviderConfig:
    """Return a deterministic fake provider config."""

    instance = ProviderConfig(
        provider="fake",
        api_key_ref=None,
        default_model="fake-default",
        narration_model="fake-narration",
        cheap_model="fake-cheap",
        pricing_mode="static_table",
    )
    return _with_overrides(instance, overrides)


def make_fake_llm_response(
    agent_name: str = "default",
    text: str = "synthetic reply",
    parsed_json: dict[str, object] | None = None,
) -> LLMResponse:
    """Return a deterministic fake LLMResponse."""

    return LLMResponse(
        text=text,
        parsed_json=parsed_json,
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        finish_reason="stop",
        cost_estimate_usd=0.0,
    )


def regenerate_fixtures(fixture_dir: Path = FIXTURE_DIR) -> None:
    """Regenerate committed eval fixtures deterministically for maintainers."""

    fixture_dir.mkdir(parents=True, exist_ok=True)
    valid_data = make_valid_saga_state().model_dump(mode="json")

    (fixture_dir / "valid_saga_state.json").write_text(
        json.dumps(valid_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    missing_field = dict(valid_data)
    missing_field.pop("campaign_id")
    (fixture_dir / "invalid_saga_state_missing_field.json").write_text(
        json.dumps(missing_field, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    bad_enum = dict(valid_data)
    bad_enum["phase"] = "unknown_phase"
    (fixture_dir / "invalid_saga_state_bad_enum.json").write_text(
        json.dumps(bad_enum, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (fixture_dir / "secret_redaction_sample.txt").write_text(
        "\n".join(
            (
                "Session setup prose that is safe.",
                "sk-or-v1-aaaaaaaaaaaaaaaaaaaa",
                "Another safe sentence.",
                "Authorization: Bearer abc1234567890xyzABCDE",
                "AKIAABCDEFGHIJKLMNOP",
                "deadbeef0123456789cafefeedfaceb00c1234567890abcdef",
                "",
            )
        ),
        encoding="utf-8",
    )
