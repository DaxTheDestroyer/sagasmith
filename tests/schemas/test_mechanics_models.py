"""Tests for mechanics schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sagasmith.schemas import CharacterSheet, CheckProposal, CheckResult, CombatantState, RollResult


def make_roll_result(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "roll_id": "roll_1",
        "seed": "seed-1",
        "die": "d20",
        "natural": 18,
        "modifier": 5,
        "total": 23,
        "dc": 20,
        "timestamp": "2026-04-26T23:00:00Z",
    }
    data.update(overrides)
    return data


def make_state_delta(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "delta_1",
        "source": "rules",
        "path": "character_sheet.current_hp",
        "operation": "increment",
        "value": -3,
        "reason": "Damage from strike.",
    }
    data.update(overrides)
    return data


def make_effect(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {"kind": "damage", "description": "3 slashing damage"}
    data.update(overrides)
    return data


def make_check_result(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "proposal_id": "proposal_1",
        "roll_result": make_roll_result(),
        "degree": "success",
        "effects": [make_effect()],
        "state_deltas": [make_state_delta()],
    }
    data.update(overrides)
    return data


def make_attack_profile(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "atk_longsword",
        "name": "Longsword",
        "modifier": 7,
        "damage": "1d8+4 slashing",
        "traits": ["versatile-p"],
        "range": None,
    }
    data.update(overrides)
    return data


def make_character_sheet(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "pc_1",
        "name": "Asha",
        "level": 1,
        "ancestry": "Human",
        "background": "Guard",
        "class_name": "Fighter",
        "abilities": {"str": 18, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
        "proficiencies": {"perception": "trained", "fortitude": "expert"},
        "max_hp": 20,
        "current_hp": 20,
        "armor_class": 18,
        "perception_modifier": 5,
        "saving_throws": {"fortitude": 7, "reflex": 5, "will": 4},
        "skills": {"athletics": 7, "intimidation": 3},
        "attacks": [make_attack_profile()],
        "inventory": [{"id": "item_1", "name": "Rations", "quantity": 3, "bulk": 0.1}],
        "conditions": [],
    }
    data.update(overrides)
    return data


def test_check_proposal_kind_literal() -> None:
    base = {
        "id": "proposal_1",
        "reason": "Climb the wall.",
        "actor_id": "pc_1",
        "target_id": None,
        "stat": "athletics",
        "modifier": 7,
        "dc": 18,
        "secret": False,
    }

    with pytest.raises(ValidationError):
        CheckProposal(**base, kind="magic")

    for kind in ["skill", "attack", "save", "initiative", "flat"]:
        assert CheckProposal(**base, kind=kind).kind == kind


def test_check_result_embeds_roll_result() -> None:
    result = CheckResult(**make_check_result())

    assert isinstance(result.roll_result, RollResult)
    assert result.degree == "success"
    assert result.effects
    assert result.state_deltas


def test_roll_result_total_is_int() -> None:
    result = RollResult(**make_roll_result())
    assert isinstance(result.total, int)

    with pytest.raises(ValidationError):
        RollResult(**make_roll_result(total=23.0))


def test_character_sheet_level_positive() -> None:
    with pytest.raises(ValidationError):
        CharacterSheet(**make_character_sheet(level=0))

    assert CharacterSheet(**make_character_sheet(level=1)).level == 1


@pytest.mark.smoke
def test_character_sheet_rejects_current_hp_above_max() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CharacterSheet(**make_character_sheet(current_hp=999))
    msg = str(exc_info.value)
    assert "current_hp" in msg
    assert "max_hp" in msg


def test_character_sheet_accepts_current_hp_equal_to_max() -> None:
    cs = CharacterSheet(**make_character_sheet(current_hp=20))
    assert cs.current_hp == 20


def test_combatant_state_rejects_current_hp_above_max() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CombatantState(
            id="c1",
            name="Goblin",
            current_hp=11,
            max_hp=10,
            armor_class=15,
        )
    msg = str(exc_info.value)
    assert "current_hp" in msg
    assert "max_hp" in msg


def test_combatant_state_accepts_current_hp_equal_to_max() -> None:
    cs = CombatantState(
        id="c1",
        name="Goblin",
        current_hp=10,
        max_hp=10,
        armor_class=15,
    )
    assert cs.current_hp == 10
