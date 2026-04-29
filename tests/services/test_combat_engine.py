"""Tests for deterministic first-slice combat engine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.common import CombatantState
from sagasmith.schemas.mechanics import CharacterSheet, CombatState, RollResult
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.dice import DiceService
from sagasmith.services.rules_engine import RulesEngine

_ALLOWED_POSITIONS = {"close", "near", "far", "behind_cover"}


class InitiativeDice:
    """Deterministic initiative rolls selected by actor id for order tests."""

    def __init__(self, naturals: dict[str, int]) -> None:
        self.naturals = naturals

    def roll_d20(
        self,
        *,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        natural = self.naturals[actor_id]
        return RollResult(
            roll_id=f"roll_{purpose}_{actor_id}_{roll_index:06d}",
            seed="combat:test",
            die="d20",
            natural=natural,
            modifier=modifier,
            total=natural + modifier,
            dc=dc,
            timestamp=datetime(2026, 4, 28, tzinfo=UTC).isoformat(),
        )


class ScriptedCombatDice:
    """Deterministic rolls selected by purpose/index for strike tests."""

    def __init__(
        self,
        d20_naturals: dict[tuple[str, str, int], int],
        damage_naturals: dict[tuple[str, str, int], int],
    ) -> None:
        self.d20_naturals = d20_naturals
        self.damage_naturals = damage_naturals

    def roll_d20(
        self,
        *,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        natural = self.d20_naturals.get((purpose, actor_id, roll_index), 10)
        return RollResult(
            roll_id=f"roll_{purpose}_{actor_id}_{roll_index:06d}",
            seed="combat:test",
            die="d20",
            natural=natural,
            modifier=modifier,
            total=natural + modifier,
            dc=dc,
            timestamp=datetime(2026, 4, 28, tzinfo=UTC).isoformat(),
        )

    def roll(
        self,
        *,
        die: str,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        natural = self.damage_naturals.get((die, actor_id, roll_index), 3)
        return RollResult(
            roll_id=f"roll_{purpose}_{actor_id}_{roll_index:06d}",
            seed="combat:test",
            die=die,
            natural=natural,
            modifier=modifier,
            total=natural + modifier,
            dc=dc,
            timestamp=datetime(2026, 4, 28, tzinfo=UTC).isoformat(),
        )


def _engine_with_dice(dice: InitiativeDice | ScriptedCombatDice | DiceService) -> CombatEngine:
    return CombatEngine(dice=dice, rules=RulesEngine(dice=dice))  # type: ignore[arg-type]


def _started_state(
    dice: ScriptedCombatDice,
) -> tuple[CombatEngine, CharacterSheet, tuple[CombatantState, CombatantState], CombatState]:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    engine = CombatEngine(dice=dice, rules=RulesEngine(dice=dice))  # type: ignore[arg-type]
    state, _ = engine.start_encounter(sheet, enemies)
    return engine, sheet, enemies, state


def test_start_encounter_rolls_initiative_and_sets_action_state() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = InitiativeDice(
        {
            sheet.id: 10,  # total 15
            enemies[0].id: 12,  # total 15, lower perception than PC
            enemies[1].id: 11,  # total 15, lower perception than PC, higher than melee
        }
    )

    state, initiative_results = _engine_with_dice(dice).start_encounter(
        sheet, enemies, roll_index=4
    )

    assert state.encounter_id == "enc_first_slice"
    assert state.round_number == 1
    assert state.active_combatant_id == sheet.id
    assert [entry.combatant_id for entry in state.initiative_order] == [
        sheet.id,
        enemies[1].id,
        enemies[0].id,
    ]
    assert [result.roll_result.roll_id for result in initiative_results] == [
        f"roll_perception_{sheet.id}_000004",
        f"roll_initiative_{enemies[0].id}_000005",
        f"roll_initiative_{enemies[1].id}_000006",
    ]
    assert all(actions == 3 for actions in state.action_counts.values())
    assert all(state.reaction_available.values())
    assert set(state.positions.values()).issubset(_ALLOWED_POSITIONS)
    assert state.positions[sheet.id] == "near"
    assert state.positions[enemies[0].id] == "close"
    assert state.positions[enemies[1].id] == "far"


def test_start_encounter_rejects_more_than_two_enemies() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    third_enemy = enemies[0].model_copy(update={"id": "enemy_extra"})
    engine = _engine_with_dice(DiceService(campaign_seed="c", session_seed="s"))

    with pytest.raises(ValueError, match="no more than two enemies"):
        engine.start_encounter(sheet, (*enemies, third_enemy))


def test_start_encounter_rejects_non_combatant_enemy_records() -> None:
    sheet = make_first_slice_character()
    engine = _engine_with_dice(DiceService(campaign_seed="c", session_seed="s"))

    with pytest.raises(ValueError, match="enemy records must be CombatantState"):
        engine.start_encounter(sheet, ({"id": "not_typed"},))  # type: ignore[arg-type]


def test_start_encounter_ties_break_by_perception_modifier_then_actor_id() -> None:
    sheet = make_first_slice_character()
    enemy_a = CombatantState(
        id="enemy_alpha",
        name="Enemy Alpha",
        current_hp=6,
        max_hp=6,
        armor_class=14,
        perception_modifier=2,
        attacks=[],
        conditions=[],
    )
    enemy_b = enemy_a.model_copy(update={"id": "enemy_beta", "name": "Enemy Beta"})
    dice = InitiativeDice({sheet.id: 1, enemy_a.id: 10, enemy_b.id: 10})

    state, _ = _engine_with_dice(dice).start_encounter(sheet, (enemy_b, enemy_a))

    assert [entry.combatant_id for entry in state.initiative_order] == [
        enemy_alpha_id := enemy_a.id,
        enemy_b.id,
        sheet.id,
    ]
    assert enemy_alpha_id < enemy_b.id


def test_resolve_strike_handles_hit_miss_and_critical_hit_with_damage_rolls() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedCombatDice(
        d20_naturals={
            ("attack_longsword", sheet.id, 10): 10,
            ("attack_longsword", sheet.id, 20): 2,
            ("attack_longsword", sheet.id, 30): 18,
        },
        damage_naturals={
            ("d8", sheet.id, 10): 3,
            ("d8", sheet.id, 30): 4,
        },
    )
    engine, _, _, state = _started_state(dice)

    hit_state, hit_check, hit_damage = engine.resolve_strike(
        state, sheet.id, enemies[0].id, "longsword", roll_index=10
    )
    assert hit_check.degree == "success"
    assert hit_damage is not None
    assert hit_state.action_counts[sheet.id] == 2
    assert f"damage_roll={hit_damage.roll_id}" in hit_check.effects[0].description
    assert "damage_roll=roll_" in hit_check.effects[0].description
    assert next(c.current_hp for c in hit_state.combatants if c.id == enemies[0].id) == 1

    miss_state, miss_check, miss_damage = engine.resolve_strike(
        state, sheet.id, enemies[0].id, "longsword", roll_index=20
    )
    assert miss_check.degree == "failure"
    assert miss_damage is None
    assert miss_check.state_deltas == []
    assert (
        next(c.current_hp for c in miss_state.combatants if c.id == enemies[0].id)
        == enemies[0].current_hp
    )

    close_second_enemy_state = state.model_copy(
        update={"positions": {**state.positions, enemies[1].id: "close"}}
    )
    critical_state, critical_check, critical_damage = engine.resolve_strike(
        close_second_enemy_state, sheet.id, enemies[1].id, "longsword", roll_index=30
    )
    assert critical_check.degree == "critical_success"
    assert critical_damage is not None
    assert critical_check.state_deltas[0].value == 0
    assert f"damage_roll={critical_damage.roll_id}" in critical_check.effects[0].description
    assert "damage_roll=roll_" in critical_check.effects[0].description
    assert f"damage={2 * critical_damage.total}" in critical_check.effects[0].description
    assert critical_check.effects[0].description.count("damage_roll=roll_") == 1
    assert next(c.current_hp for c in critical_state.combatants if c.id == enemies[1].id) == 0


def test_resolve_strike_rejects_invalid_melee_range_without_consuming_action() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedCombatDice({}, {})
    engine, _, _, state = _started_state(dice)
    state = state.model_copy(update={"positions": {**state.positions, enemies[0].id: "near"}})

    with pytest.raises(ValueError, match="requires close range"):
        engine.resolve_strike(state, sheet.id, enemies[0].id, "longsword", roll_index=1)

    assert state.action_counts[sheet.id] == 3


def test_move_rejects_current_position_without_decrementing_actions() -> None:
    sheet = make_first_slice_character()
    dice = ScriptedCombatDice({}, {})
    engine, _, _, state = _started_state(dice)

    with pytest.raises(ValueError, match="already at"):
        engine.move(state, sheet.id, state.positions[sheet.id])

    assert state.action_counts[sheet.id] == 3


def test_end_turn_skips_defeated_combatants_and_resets_reaction() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedCombatDice({}, {})
    engine, _, _, state = _started_state(dice)
    defeated = enemies[0].model_copy(update={"current_hp": 0})
    living = enemies[1]
    state = state.model_copy(
        update={
            "active_combatant_id": sheet.id,
            "combatants": [state.combatants[0], defeated, living],
            "initiative_order": state.initiative_order,
            "action_counts": {**state.action_counts, living.id: 0},
            "reaction_available": {**state.reaction_available, living.id: False},
        }
    )

    next_state = engine.end_turn(state)

    assert next_state.active_combatant_id == living.id
    assert next_state.action_counts[living.id] == 3
    assert next_state.reaction_available[living.id] is True


def test_is_encounter_complete_when_pc_or_all_enemies_are_defeated() -> None:
    enemies = make_first_slice_enemies()
    dice = ScriptedCombatDice({}, {})
    engine, _, _, state = _started_state(dice)

    assert not engine.is_encounter_complete(state)

    defeated_enemies = [
        state.combatants[0],
        *(enemy.model_copy(update={"current_hp": 0}) for enemy in enemies),
    ]
    assert engine.is_encounter_complete(state.model_copy(update={"combatants": defeated_enemies}))

    defeated_pc = [state.combatants[0].model_copy(update={"current_hp": 0}), *enemies]
    assert engine.is_encounter_complete(state.model_copy(update={"combatants": defeated_pc}))
