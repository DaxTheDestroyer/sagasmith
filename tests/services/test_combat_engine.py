"""Tests for deterministic first-slice combat engine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.common import CombatantState
from sagasmith.schemas.mechanics import RollResult
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


def _engine_with_dice(dice: InitiativeDice | DiceService) -> CombatEngine:
    return CombatEngine(dice=dice, rules=RulesEngine(dice=dice))  # type: ignore[arg-type]


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

    state, initiative_results = _engine_with_dice(dice).start_encounter(sheet, enemies, roll_index=4)

    assert state.encounter_id == "enc_first_slice"
    assert state.round_number == 1
    assert state.active_combatant_id == sheet.id
    assert [entry.combatant_id for entry in state.initiative_order] == [
        sheet.id,
        enemies[1].id,
        enemies[0].id,
    ]
    assert [result.roll_result.roll_id for result in initiative_results] == [
        f"roll_initiative_{sheet.id}_000004",
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
