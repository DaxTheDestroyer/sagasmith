"""QA-03 deterministic rules-first mechanics gate."""

from __future__ import annotations

from datetime import UTC, datetime

from sagasmith.evals.harness import run_smoke
from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.mechanics import RollResult
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.dice import DiceService
from sagasmith.services.pf2e import compute_degree
from sagasmith.services.rules_engine import RulesEngine


class ScriptedDice:
    """Deterministic dice for scenario-focused QA-03 combat assertions."""

    def __init__(self) -> None:
        self.d20_by_key: dict[tuple[str, str, int], int] = {}
        self.damage_by_key: dict[tuple[str, str, int], int] = {}

    def roll_d20(
        self,
        *,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        natural = self.d20_by_key.get((purpose, actor_id, roll_index), 10)
        return RollResult(
            roll_id=f"roll_{purpose}_{actor_id}_{roll_index:06d}",
            seed="qa03:scripted",
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
        natural = self.damage_by_key.get((die, actor_id, roll_index), 4)
        return RollResult(
            roll_id=f"roll_{purpose}_{actor_id}_{roll_index:06d}",
            seed="qa03:scripted",
            die=die,
            natural=natural,
            modifier=modifier,
            total=natural + modifier,
            dc=dc,
            timestamp=datetime(2026, 4, 28, tzinfo=UTC).isoformat(),
        )


def _scripted_engine(dice: ScriptedDice) -> tuple[CombatEngine, RulesEngine]:
    rules = RulesEngine(dice=dice)  # type: ignore[arg-type]
    return CombatEngine(dice=dice, rules=rules), rules  # type: ignore[arg-type]


def test_qa03_degree_boundaries() -> None:
    assert compute_degree(natural=10, total=15, dc=15) == "success"
    assert compute_degree(natural=10, total=14, dc=15) == "failure"
    assert compute_degree(natural=10, total=25, dc=15) == "critical_success"
    assert compute_degree(natural=10, total=5, dc=15) == "critical_failure"
    assert compute_degree(natural=20, total=14, dc=15) == "success"
    assert compute_degree(natural=20, total=15, dc=15) == "critical_success"
    assert compute_degree(natural=1, total=25, dc=15) == "success"
    assert compute_degree(natural=1, total=15, dc=15) == "failure"


def test_qa03_seeded_replay() -> None:
    dice1 = DiceService(campaign_seed="qa03", session_seed="session")
    dice2 = DiceService(campaign_seed="qa03", session_seed="session")

    d20_1 = dice1.roll_d20(purpose="athletics", actor_id="pc", modifier=7, roll_index=0, dc=15)
    d20_2 = dice2.roll_d20(purpose="athletics", actor_id="pc", modifier=7, roll_index=0, dc=15)
    d8_1 = dice1.roll(die="d8", purpose="damage_longsword", actor_id="pc", modifier=4, roll_index=1)
    d8_2 = dice2.roll(die="d8", purpose="damage_longsword", actor_id="pc", modifier=4, roll_index=1)

    assert (d20_1.roll_id, d20_1.natural, d20_1.total) == (d20_2.roll_id, d20_2.natural, d20_2.total)
    assert (d8_1.roll_id, d8_1.natural, d8_1.total) == (d8_2.roll_id, d8_2.natural, d8_2.total)


def test_qa03_skill_check() -> None:
    sheet = make_first_slice_character()
    engine = RulesEngine(dice=DiceService(campaign_seed="qa03", session_seed="skill"))

    result = engine.resolve_check(sheet, stat="athletics", dc=15, reason="QA-03 skill", roll_index=2)

    assert result.proposal_id == "check_athletics_000002"
    assert result.roll_result.roll_id == "roll_athletics_pc_valeros_first_slice_000002"
    assert result.roll_result.modifier == sheet.skills["athletics"]
    assert result.roll_result.dc == 15


def test_qa03_initiative() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedDice()
    dice.d20_by_key = {
        ("perception", sheet.id, 4): 10,
        ("initiative", enemies[0].id, 5): 12,
        ("initiative", enemies[1].id, 6): 11,
    }
    combat, _rules = _scripted_engine(dice)

    state, initiative = combat.start_encounter(sheet, enemies, roll_index=4)

    assert [entry.combatant_id for entry in state.initiative_order] == [sheet.id, enemies[1].id, enemies[0].id]
    assert [result.roll_result.roll_id for result in initiative] == [
        "roll_perception_pc_valeros_first_slice_000004",
        "roll_initiative_enemy_weak_melee_000005",
        "roll_initiative_enemy_weak_ranged_000006",
    ]


def test_qa03_strike_and_hp_damage() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedDice()
    dice.d20_by_key[("attack_longsword", sheet.id, 10)] = 12
    dice.damage_by_key[("d8", sheet.id, 10)] = 4
    combat, _rules = _scripted_engine(dice)
    state, _initiative = combat.start_encounter(sheet, enemies)

    updated, attack, damage = combat.resolve_strike(state, sheet.id, enemies[0].id, "longsword", roll_index=10)

    assert attack.degree == "success"
    assert attack.roll_result.roll_id == "roll_attack_longsword_pc_valeros_first_slice_000010"
    assert damage is not None
    assert damage.roll_id == "roll_damage_longsword_pc_valeros_first_slice_000010"
    assert attack.state_deltas[0].path == "combatants.enemy_weak_melee.current_hp"
    assert attack.state_deltas[0].value == 0
    assert next(combatant.current_hp for combatant in updated.combatants if combatant.id == enemies[0].id) == 0
    assert updated.action_counts[sheet.id] == 2
    assert "damage_roll=roll_damage_longsword_pc_valeros_first_slice_000010" in attack.effects[0].description


def test_qa03_roll_log_completeness() -> None:
    sheet = make_first_slice_character()
    enemies = make_first_slice_enemies()
    dice = ScriptedDice()
    dice.d20_by_key[("attack_longsword", sheet.id, 20)] = 12
    dice.damage_by_key[("d8", sheet.id, 20)] = 4
    combat, _rules = _scripted_engine(dice)

    state, initiative = combat.start_encounter(sheet, enemies, roll_index=7)
    _updated, attack, damage = combat.resolve_strike(state, sheet.id, enemies[0].id, "longsword", roll_index=20)

    produced_roll_ids = [result.roll_result.roll_id for result in initiative]
    produced_roll_ids.append(attack.roll_result.roll_id)
    if damage is not None:
        produced_roll_ids.append(damage.roll_id)

    assert len(produced_roll_ids) == 5
    assert len(set(produced_roll_ids)) == len(produced_roll_ids)
    assert all(roll_id.startswith("roll_") for roll_id in produced_roll_ids)
    assert {roll_id.split("_")[1] for roll_id in produced_roll_ids} >= {"perception", "initiative", "attack", "damage"}
    assert all(result.roll_result.total == result.roll_result.natural + result.roll_result.modifier for result in initiative)
    assert attack.roll_result.total == attack.roll_result.natural + attack.roll_result.modifier
    assert damage is not None and damage.total == damage.natural + damage.modifier


def test_rules_first_vertical_slice_smoke_harness_check_registered() -> None:
    result = run_smoke()
    check = next(check for check in result.checks if check.name == "rules_first_vertical_slice")
    assert check.ok, check.detail
