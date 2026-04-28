"""Tests for first-slice PF2e character and enemy data."""

from __future__ import annotations

from sagasmith.rules import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.common import CombatantState
from sagasmith.schemas.mechanics import CharacterSheet


def test_make_first_slice_character_returns_valid_valeros_sheet() -> None:
    sheet = make_first_slice_character()

    assert sheet.id == "pc_valeros_first_slice"
    assert sheet.name == "Valeros"
    assert sheet.level == 1
    assert sheet.class_name == "Fighter"
    assert sheet.current_hp == 20
    assert sheet.max_hp == 20
    assert sheet.armor_class == 18
    assert sheet.perception_modifier == 5
    assert sheet.saving_throws == {"fortitude": 7, "reflex": 5, "will": 4}
    assert CharacterSheet.model_validate(sheet.model_dump()) == sheet


def test_make_first_slice_character_pins_trained_skills_and_attacks() -> None:
    sheet = make_first_slice_character()

    assert list(sheet.skills)[:4] == ["athletics", "intimidation", "survival", "acrobatics"]
    assert len(sheet.skills) >= 4
    assert len(sheet.attacks) == 2

    melee, ranged = sheet.attacks
    assert melee.id == "longsword"
    assert melee.name == "longsword"
    assert melee.modifier == 7
    assert melee.damage == "1d8+4 slashing"
    assert melee.range is None

    assert ranged.id == "shortbow"
    assert ranged.name == "shortbow"
    assert ranged.modifier == 5
    assert ranged.damage == "1d6 piercing"
    assert ranged.range == "60 feet"


def test_make_first_slice_enemies_returns_two_valid_combatants() -> None:
    enemies = make_first_slice_enemies()

    assert len(enemies) == 2
    assert tuple(enemy.id for enemy in enemies) == ("enemy_weak_melee", "enemy_weak_ranged")
    for enemy in enemies:
        assert isinstance(enemy, CombatantState)
        assert CombatantState.model_validate(enemy.model_dump()) == enemy
        assert enemy.armor_class > 0
        assert enemy.max_hp > 0
        assert enemy.current_hp == enemy.max_hp
        assert hasattr(enemy, "attacks") is False
