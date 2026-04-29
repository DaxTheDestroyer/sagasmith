"""Phase 5 RulesLawyer deterministic first-slice mechanics tests."""

from __future__ import annotations

import copy

import pytest

from sagasmith.agents.rules_lawyer.node import rules_lawyer_node
from sagasmith.app.paths import CampaignPaths
from sagasmith.evals.fixtures import make_valid_saga_state
from sagasmith.graph.bootstrap import AgentServices
from sagasmith.rules.first_slice import make_first_slice_character
from sagasmith.schemas.campaign import CampaignManifest
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.tui.app import SagaSmithApp


class ExplodingLLM:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"RulesLawyer touched services.llm.{name}")


@pytest.fixture
def services() -> AgentServices:
    return AgentServices(
        dice=DiceService(campaign_seed="phase5", session_seed="rules-lawyer"),
        cost=CostGovernor(session_budget_usd=1.0),
        llm=ExplodingLLM(),
    )


def _state(player_input: str, **overrides: object) -> dict[str, object]:
    base = make_valid_saga_state(
        pending_player_input=player_input,
        character_sheet=make_first_slice_character(),
        check_results=[],
        pending_narration=[],
        combat_state=None,
    ).model_dump()
    base.update(overrides)
    return base


def test_roll_check_parser_is_case_and_whitespace_normalized(services: AgentServices) -> None:
    lower = rules_lawyer_node(_state("roll athletics dc 15"), services)
    loud = rules_lawyer_node(_state("  ROLL   ATHLETICS   DC   15  "), services)

    assert len(lower["check_results"]) == 1
    assert len(loud["check_results"]) == 1
    assert lower["check_results"][0]["proposal_id"].startswith("check_athletics_")
    assert loud["check_results"][0]["proposal_id"].startswith("check_athletics_")


def test_supported_skill_and_perception_checks_append_one_result(services: AgentServices) -> None:
    for text, expected in [
        ("check acrobatics dc 14", "check_acrobatics_"),
        ("roll survival dc 13", "check_survival_"),
        ("check intimidation dc 16", "check_intimidation_"),
        ("perception dc 17", "check_perception_"),
    ]:
        result = rules_lawyer_node(_state(text), services)
        assert len(result["check_results"]) == 1
        assert result["check_results"][0]["proposal_id"].startswith(expected)


def test_unsupported_input_returns_visible_rules_error_without_roll(
    services: AgentServices,
) -> None:
    result = rules_lawyer_node(_state("roll arcana dc 15"), services)

    assert result["check_results"] == []
    assert result["pending_narration"]
    assert "Rules error:" in result["pending_narration"][0]


def test_start_combat_creates_state_and_initiative_results(services: AgentServices) -> None:
    result = rules_lawyer_node(_state("start combat"), services)

    combat_state = result["combat_state"]
    assert combat_state["encounter_id"] == "enc_first_slice"
    assert len(combat_state["combatants"]) == 3
    enemies = [
        combatant
        for combatant in combat_state["combatants"]
        if combatant["id"].startswith("enemy_")
    ]
    assert len(enemies) <= 2
    assert len(result["check_results"]) == 3


def test_strike_resolves_through_combat_engine_and_records_damage_roll_id(
    services: AgentServices,
) -> None:
    started = rules_lawyer_node(_state("start combat"), services)
    state = _state(
        "strike enemy_weak_melee with longsword",
        combat_state=started["combat_state"],
        check_results=started["check_results"],
    )

    result = rules_lawyer_node(state, services)

    assert len(result["check_results"]) == 4
    assert result["check_results"][-1]["proposal_id"].startswith("check_attack_longsword_")
    assert result["combat_state"]["action_counts"]["pc_valeros_first_slice"] == 2
    if result["check_results"][-1]["effects"]:
        assert any("damage_roll=" in line for line in result["pending_narration"])


def test_invalid_combat_action_value_error_returns_visible_error(services: AgentServices) -> None:
    started = rules_lawyer_node(_state("start combat"), services)
    result = rules_lawyer_node(
        _state(
            "strike enemy_weak_ranged with longsword",
            combat_state=started["combat_state"],
            check_results=started["check_results"],
        ),
        services,
    )

    assert result["check_results"] == started["check_results"]
    assert "Rules error:" in result["pending_narration"][0]


def test_rejects_pc_as_strike_target_without_roll(services: AgentServices) -> None:
    started = rules_lawyer_node(_state("start combat"), services)
    result = rules_lawyer_node(
        _state(
            "strike pc_valeros_first_slice with longsword",
            combat_state=started["combat_state"],
            check_results=started["check_results"],
        ),
        services,
    )

    assert result["check_results"] == started["check_results"]
    assert "Rules error:" in result["pending_narration"][0]


def test_rules_lawyer_does_not_mutate_input_or_touch_llm(services: AgentServices) -> None:
    state = _state("roll athletics dc 15")
    before = copy.deepcopy(state)

    rules_lawyer_node(state, services)

    assert state == before


def test_completed_combat_returns_phase_to_play(services: AgentServices) -> None:
    started = rules_lawyer_node(_state("start combat"), services)
    combat_state = copy.deepcopy(started["combat_state"])
    for combatant in combat_state["combatants"]:
        if combatant["id"] == "enemy_weak_melee":
            combatant["current_hp"] = 1
            combatant["armor_class"] = 1
        elif combatant["id"].startswith("enemy_"):
            combatant["current_hp"] = 0

    result = rules_lawyer_node(
        _state(
            "strike enemy_weak_melee with longsword",
            combat_state=combat_state,
            check_results=started["check_results"],
        ),
        services,
    )

    assert result["phase"] == "play"
    assert "Combat complete" in result["pending_narration"][-1]


def test_tui_build_play_state_seeds_first_slice_sheet_and_preserves_existing(tmp_path) -> None:
    manifest = CampaignManifest(
        campaign_id="cmp_phase5_001",
        campaign_name="Phase 5",
        campaign_slug="phase-5",
        created_at="2026-04-28T00:00:00+00:00",
        sagasmith_version="0.0.1",
        schema_version=1,
        manifest_version=1,
    )
    app = SagaSmithApp(
        paths=CampaignPaths(
            root=tmp_path,
            manifest=tmp_path / "campaign.toml",
            db=tmp_path / "campaign.sqlite",
            player_vault=tmp_path / "player_vault",
        ),
        manifest=manifest,
    )

    state = app._build_play_state("roll athletics dc 15")  # pyright: ignore[reportPrivateUsage]

    assert state["character_sheet"] == make_first_slice_character().model_dump()
    existing_sheet = {**make_first_slice_character().model_dump(), "current_hp": 7}
    preserved = app._build_play_state(  # pyright: ignore[reportPrivateUsage]
        "look",
        current_state={"character_sheet": existing_sheet},
    )
    assert preserved["character_sheet"] == existing_sheet
