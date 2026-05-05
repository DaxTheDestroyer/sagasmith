"""Tests for the Rules Turn Resolution Module Interface.

All tests call resolve_rules_turn directly - no LangGraph or Textual plumbing.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from sagasmith.evals.fixtures import make_valid_saga_state
from sagasmith.graph.bootstrap import default_skill_store
from sagasmith.providers import DeterministicFakeClient
from sagasmith.rules.first_slice import make_first_slice_character
from sagasmith.rules_turn_resolution import RulesTurnContext, resolve_rules_turn
from sagasmith.schemas.mechanics import CombatState
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.services.errors import BudgetStopError


class ExplodingLLM:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"Rules Turn Resolution touched llm.{name}")


@pytest.fixture
def dice() -> DiceService:
    return DiceService(campaign_seed="rules-turn", session_seed="resolution")


@pytest.fixture
def cost() -> CostGovernor:
    return CostGovernor(session_budget_usd=1.0)


def _state(player_input: str | None, **overrides: object) -> dict[str, Any]:
    base = make_valid_saga_state(
        pending_player_input=player_input,
        character_sheet=make_first_slice_character(),
        check_results=[],
        pending_narration=[],
        combat_state=None,
    ).model_dump()
    base.update(overrides)
    return base


def _resolve(
    state: dict[str, Any],
    dice: DiceService,
    cost: CostGovernor,
    *,
    llm: object | None = None,
    skill_store: object | None = None,
):
    return resolve_rules_turn(
        RulesTurnContext(
            state=state,
            dice=dice,
            cost=cost,
            llm=llm,
            skill_store=skill_store,
        )
    )


def test_no_pending_player_input_returns_empty_updates(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state(None), dice, cost)

    assert result.state_updates == {}
    assert result.skills_activated == ()


def test_explicit_skill_check_appends_one_result_and_skill(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state("roll athletics dc 15"), dice, cost)

    assert len(result.state_updates["check_results"]) == 1
    assert result.state_updates["check_results"][0]["proposal_id"].startswith("check_athletics_")
    assert result.skills_activated == ("skill-check-resolution",)


def test_perception_check_appends_one_result(dice: DiceService, cost: CostGovernor) -> None:
    result = _resolve(_state("perception dc 17"), dice, cost)

    assert len(result.state_updates["check_results"]) == 1
    assert result.state_updates["check_results"][0]["proposal_id"].startswith("check_perception_")


def test_natural_language_skill_action_resolves_without_llm(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state("I climb the slick cliff"), dice, cost, llm=ExplodingLLM())

    assert result.state_updates["check_results"][0]["proposal_id"].startswith("check_athletics_")


def test_non_mechanical_player_input_returns_empty_updates(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state("I tell the child a quiet story"), dice, cost)

    assert result.state_updates == {}
    assert result.skills_activated == ()


def test_unsupported_mechanical_input_returns_visible_rules_error_without_roll(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state("roll arcana dc 15"), dice, cost)

    assert result.state_updates["check_results"] == []
    assert result.state_updates["pending_narration"]
    assert "Rules error:" in result.state_updates["pending_narration"][0]


def test_budget_fallback_returns_explicit_check_hint(dice: DiceService, cost: CostGovernor) -> None:
    class BlockingCostGovernor(CostGovernor):
        def preflight(self, **kwargs):  # type: ignore[no-untyped-def]
            raise BudgetStopError("blocked")

    result = _resolve(
        _state("I carefully inspect the strange mechanism"),
        dice,
        BlockingCostGovernor(session_budget_usd=0.0),
        llm=DeterministicFakeClient({}),
    )

    assert result.state_updates["pending_narration"] == [
        "I didn't catch that — try `/check athletics 15`."
    ]


def test_start_combat_creates_state_initiative_phase_and_skill(
    dice: DiceService, cost: CostGovernor
) -> None:
    result = _resolve(_state("start combat"), dice, cost)

    combat_state = result.state_updates["combat_state"]
    assert combat_state["encounter_id"] == "enc_first_slice"
    assert len(combat_state["combatants"]) == 3
    assert len(result.state_updates["check_results"]) == 3
    assert result.state_updates["phase"] == "combat"
    assert result.skills_activated == ("combat-resolution",)


def test_strike_consumes_action_and_records_damage_audit_when_damage_occurs(
    dice: DiceService, cost: CostGovernor
) -> None:
    started = _resolve(_state("start combat"), dice, cost)
    state = _state(
        "strike enemy_weak_melee with longsword",
        combat_state=started.state_updates["combat_state"],
        check_results=started.state_updates["check_results"],
    )

    result = _resolve(state, dice, cost)

    assert len(result.state_updates["check_results"]) == 4
    assert result.state_updates["check_results"][-1]["proposal_id"].startswith(
        "check_attack_longsword_"
    )
    assert result.state_updates["combat_state"]["action_counts"]["pc_valeros_first_slice"] == 2
    if result.state_updates["check_results"][-1]["effects"]:
        assert any("damage_roll=" in line for line in result.state_updates["pending_narration"])


def test_invalid_strike_preserves_existing_checks_and_returns_visible_error(
    dice: DiceService, cost: CostGovernor
) -> None:
    started = _resolve(_state("start combat"), dice, cost)
    result = _resolve(
        _state(
            "strike enemy_weak_ranged with longsword",
            combat_state=started.state_updates["combat_state"],
            check_results=started.state_updates["check_results"],
        ),
        dice,
        cost,
    )

    assert result.state_updates["check_results"] == started.state_updates["check_results"]
    assert "Rules error:" in result.state_updates["pending_narration"][0]


def test_move_updates_position_and_consumes_action(dice: DiceService, cost: CostGovernor) -> None:
    started = _resolve(_state("start combat"), dice, cost)
    result = _resolve(
        _state(
            "move close",
            combat_state=started.state_updates["combat_state"],
            check_results=started.state_updates["check_results"],
        ),
        dice,
        cost,
    )

    assert result.state_updates["combat_state"]["positions"]["pc_valeros_first_slice"] == "close"
    assert result.state_updates["combat_state"]["action_counts"]["pc_valeros_first_slice"] == 2


def test_end_turn_advances_active_combatant(dice: DiceService, cost: CostGovernor) -> None:
    started = _resolve(_state("start combat"), dice, cost)
    combat_state = CombatState.model_validate(started.state_updates["combat_state"])

    result = _resolve(
        _state(
            "end turn",
            combat_state=combat_state.model_dump(),
            check_results=started.state_updates["check_results"],
        ),
        dice,
        cost,
    )

    assert (
        result.state_updates["combat_state"]["active_combatant_id"]
        != combat_state.active_combatant_id
    )


def test_completed_combat_returns_phase_to_play(dice: DiceService, cost: CostGovernor) -> None:
    started = _resolve(_state("start combat"), dice, cost)
    combat_state = copy.deepcopy(started.state_updates["combat_state"])
    for combatant in combat_state["combatants"]:
        if combatant["id"] == "enemy_weak_melee":
            combatant["current_hp"] = 1
            combatant["armor_class"] = 1
        elif combatant["id"].startswith("enemy_"):
            combatant["current_hp"] = 0

    result = _resolve(
        _state(
            "strike enemy_weak_melee with longsword",
            combat_state=combat_state,
            check_results=started.state_updates["check_results"],
        ),
        dice,
        cost,
    )

    assert result.state_updates["phase"] == "play"
    assert "Combat complete" in result.state_updates["pending_narration"][-1]


def test_input_state_is_not_mutated(dice: DiceService, cost: CostGovernor) -> None:
    state = _state("roll athletics dc 15")
    before = copy.deepcopy(state)

    _resolve(state, dice, cost)

    assert state == before


def test_real_skill_store_records_skill_activation(dice: DiceService, cost: CostGovernor) -> None:
    result = _resolve(_state("roll athletics dc 15"), dice, cost, skill_store=default_skill_store())

    assert result.skills_activated == ("skill-check-resolution",)
