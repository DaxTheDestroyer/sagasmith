"""Canonical offline fixtures for schema, smoke, and regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sagasmith.schemas import (
    AttackProfile,
    BudgetPolicy,
    CampaignSeed,
    CharacterSheet,
    ContentPolicy,
    CostState,
    GameClock,
    HouseRules,
    InventoryItem,
    LLMResponse,
    MagicRulesContext,
    MemoryEntityRef,
    MemoryPacket,
    PlayerProfile,
    PlotHook,
    ProviderConfig,
    SagaState,
    SceneBrief,
    SeedArc,
    SeedCharacter,
    SessionState,
    TokenUsage,
    WorldBible,
    WorldConflict,
    WorldFaction,
    WorldLocation,
    WorldNpc,
)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _with_overrides[T: BaseModel](instance: T, overrides: dict[str, Any]) -> T:
    if not overrides:
        return instance
    merged = instance.model_dump()
    merged.update(overrides)
    return type(instance).model_validate(merged)


def with_overrides[T: BaseModel](instance: T, overrides: dict[str, Any]) -> T:
    """Public test helper wrapper around fixture override revalidation."""
    return _with_overrides(instance, overrides)


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


def make_valid_scene_brief(**overrides: Any) -> SceneBrief:
    """Return a deterministic planning-only Oracle scene brief."""

    instance = SceneBrief(
        scene_id="scene_rivermouth_001",
        intent="Investigate the missing barge at the old ford.",
        location="Rivermouth old ford",
        present_entities=["npc_mira_warden"],
        beats=["Establish riverbank clues", "Invite a social or survival approach"],
        beat_ids=["beat_riverbank_clues", "beat_choose_approach"],
        success_outs=["The trail into Copperwood becomes actionable."],
        failure_outs=["A rival witness complicates the investigation."],
        pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        callbacks_seeded=["cb_missing_barge_witness"],
        callbacks_payoff_candidates=[],
        mechanical_triggers=[],
        content_warnings=[],
    )
    return _with_overrides(instance, overrides)


def make_valid_world_bible(**overrides: Any) -> WorldBible:
    """Return a deterministic hidden world bible fixture."""

    instance = WorldBible(
        theme="Hopeful frontier mystery",
        tone=["heroic", "hopeful"],
        genre_elements=["high_fantasy", "riverside_market", "ancient_ruins"],
        core_themes=["community under pressure", "forgotten oaths returning"],
        key_locations=[
            WorldLocation(
                id="loc_rivermouth",
                name="Rivermouth",
                description="A market town where river barges meet old forest roads.",
                tags=["town", "social"],
                secrets=["The old ford hides a sealed shrine."],
            ),
            WorldLocation(
                id="loc_copperwood",
                name="Copperwood",
                description="A misty woodland threaded with abandoned waystones.",
                tags=["forest", "exploration"],
            ),
        ],
        factions=[
            WorldFaction(
                id="fac_barge_guild",
                name="Barge Guild",
                public_face="Practical merchants keeping trade moving.",
                agenda="Control access to the river crossing before rivals arrive.",
                relationships=["Tense with shrine wardens."],
            )
        ],
        important_npcs=[
            WorldNpc(
                id="npc_mira_warden",
                name="Mira",
                role="Shrine warden",
                motivation="Keep the sealed shrine from becoming a battlefield.",
                faction_id="fac_barge_guild",
            )
        ],
        core_conflicts=[
            WorldConflict(
                id="conf_shrine_rights",
                name="Rights to the Old Ford",
                summary="Trade interests and local guardians both need the shrine route.",
                stakes="If mishandled, Rivermouth loses its safest road.",
                involved_factions=["fac_barge_guild"],
            )
        ],
        magic_rules=MagicRulesContext(
            magic_prevalence="common but localized",
            divine_presence="felt through oaths and shrines",
            technology_level="late medieval fantasy",
            pf2e_assumptions=["level 1 martial first slice", "deterministic rules own mechanics"],
        ),
        safety_notes=["Avoid hard limits from content policy."],
    )
    return _with_overrides(instance, overrides)


def make_valid_campaign_seed(**overrides: Any) -> CampaignSeed:
    """Return a deterministic campaign seed fixture."""

    instance = CampaignSeed(
        plot_hooks=[
            PlotHook(
                id="hook_missing_barge",
                title="The Missing Barge",
                premise="A grain barge vanishes near the old ford before market day.",
                aligned_preferences=["exploration", "social"],
                initial_location_id="loc_rivermouth",
                featured_npc_ids=["npc_mira_warden"],
                conflict_id="conf_shrine_rights",
            ),
            PlotHook(
                id="hook_waystone_song",
                title="The Singing Waystone",
                premise="A waystone begins humming the hero's name at dusk.",
                aligned_preferences=["mystery", "exploration"],
            ),
            PlotHook(
                id="hook_guild_debt",
                title="The Guild's Unpaid Debt",
                premise="A merchant asks for discreet help before a public reckoning.",
                aligned_preferences=["social", "moral_ambiguity_ok"],
            ),
        ],
        selected_arc=SeedArc(
            title="Secrets at the Old Ford",
            selected_hook_id="hook_missing_barge",
            opening_situation="The hero is asked to inspect the riverbank before panic spreads.",
            early_beats=["Question witnesses", "Follow tracks into Copperwood"],
            likely_escalations=["A rival claims the barge was stolen by wardens."],
        ),
        key_characters=[
            SeedCharacter(
                id="npc_mira_warden",
                name="Mira",
                role="Shrine warden",
                motivation="Prevent outsiders from breaking the shrine seal.",
                first_appearance="Watching the riverbank from the old ford.",
            )
        ],
        initial_conflicts=["Trade urgency versus local sacred duty"],
        opening_questions=["Who benefits if Rivermouth blames the wardens?"],
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
        world_bible=None,
        campaign_seed=None,
        character_sheet=make_valid_character_sheet(),
        session_state=make_valid_session_state(),
        combat_state=None,
        pending_player_input=None,
        memory_packet=None,
        scene_brief=None,
        resolved_beat_ids=[],
        oracle_bypass_detected=False,
        check_results=[],
        state_deltas=[],
        pending_conflicts=[],
        pending_narration=[],
        safety_events=[],
        cost_state=make_valid_cost_state(),
        last_interrupt=None,
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
