"""Deterministic first-slice combat state transitions."""

from __future__ import annotations

from dataclasses import dataclass

from sagasmith.schemas.common import (
    AttackProfile,
    CombatantState,
    Effect,
    InitiativeEntry,
    PositionTagValue,
)
from sagasmith.schemas.deltas import StateDelta
from sagasmith.schemas.mechanics import CharacterSheet, CheckResult, CombatState, RollResult
from sagasmith.services.dice import DiceService
from sagasmith.services.pf2e import compute_degree
from sagasmith.services.rules_engine import RulesEngine

_ALLOWED_POSITIONS = {"close", "near", "far", "behind_cover"}


@dataclass(frozen=True)
class CombatEngine:
    """Resolve first-slice theater-of-mind combat mechanics deterministically."""

    dice: DiceService
    rules: RulesEngine

    def start_encounter(
        self,
        sheet: CharacterSheet,
        enemies: tuple[CombatantState, ...],
        *,
        encounter_id: str = "enc_first_slice",
        roll_index: int = 0,
    ) -> tuple[CombatState, list[CheckResult]]:
        """Start combat with initiative, action counts, reactions, and positions."""

        if len(enemies) > 2:
            raise ValueError("first-slice combat supports no more than two enemies")
        if any(not isinstance(enemy, CombatantState) for enemy in enemies):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("enemy records must be CombatantState")

        pc = _combatant_from_sheet(sheet)
        combatants = (pc, *enemies)
        initiative_results = self._roll_initiative(sheet, enemies, roll_index=roll_index)
        modifier_by_id = {combatant.id: combatant.perception_modifier for combatant in combatants}
        initiative_entries = [
            InitiativeEntry(combatant_id=combatant_id, initiative=total)
            for combatant_id, total in sorted(
                (
                    (_actor_id_from_roll_id(result.roll_result.roll_id), result.roll_result.total)
                    for result in initiative_results
                ),
                key=lambda item: (-item[1], -modifier_by_id[item[0]], item[0]),
            )
        ]

        positions: dict[str, PositionTagValue] = {pc.id: "near"}
        for idx, enemy in enumerate(enemies):
            positions[enemy.id] = "close" if idx == 0 else "far"
        if not set(positions.values()).issubset(_ALLOWED_POSITIONS):
            raise ValueError("unsupported combat position")

        return (
            CombatState(
                encounter_id=encounter_id,
                round_number=1,
                active_combatant_id=initiative_entries[0].combatant_id,
                initiative_order=initiative_entries,
                combatants=list(combatants),
                positions=positions,
                action_counts={combatant.id: 3 for combatant in combatants},
                reaction_available={combatant.id: True for combatant in combatants},
            ),
            initiative_results,
        )

    def resolve_strike(
        self,
        state: CombatState,
        actor_id: str,
        target_id: str,
        attack_id: str,
        *,
        roll_index: int,
    ) -> tuple[CombatState, CheckResult, RollResult | None]:
        """Resolve one Strike, consuming an action and returning attack/damage rolls."""

        actor = _find_combatant(state, actor_id)
        target = _find_combatant(state, target_id)
        _require_actions(state, actor_id)
        attack = _find_attack(actor, attack_id)
        target_position = state.positions.get(target_id)
        if target_position not in _ALLOWED_POSITIONS:
            raise ValueError(f"unsupported position for {target_id}: {target_position}")

        dc = target.armor_class
        if attack.range is None:
            if target_position != "close":
                raise ValueError(f"{target_id} is {target_position}; this action requires close range")
        elif target_position == "behind_cover":
            dc += 2

        attack_roll = self.dice.roll_d20(
            purpose=f"attack_{attack.id}",
            actor_id=actor_id,
            modifier=attack.modifier,
            roll_index=roll_index,
            dc=dc,
        )
        degree = compute_degree(natural=attack_roll.natural, total=attack_roll.total, dc=dc)
        damage_roll: RollResult | None = None
        effects: list[Effect] = []
        deltas: list[StateDelta] = []
        new_hp = target.current_hp

        if degree in ("success", "critical_success"):
            die, modifier = _damage_die_and_modifier(attack)
            damage_roll = self.dice.roll(
                die=die,
                purpose=f"damage_{attack.id}",
                actor_id=actor_id,
                modifier=modifier,
                roll_index=roll_index,
            )
            damage = damage_roll.total * (2 if degree == "critical_success" else 1)
            new_hp = max(0, target.current_hp - damage)
            delta_label = f"damage={damage}"
            cover_text = "; behind_cover +2 AC" if target_position == "behind_cover" else ""
            effects.append(
                Effect(
                    kind="hp_delta",
                    description=(
                        f"{target_id}: HP {target.current_hp} -> {new_hp} "
                        f"({delta_label}; damage_roll={damage_roll.roll_id}{cover_text})"
                    ),
                    target_id=target_id,
                )
            )
            deltas.append(
                StateDelta(
                    id=f"delta_strike_{actor_id}_{target_id}_{roll_index:06d}",
                    source="rules",
                    path=f"combatants.{target_id}.current_hp",
                    operation="set",
                    value=new_hp,
                    reason="Strike damage",
                )
            )

        updated_state = _replace_combatant(
            state,
            target_id,
            target.model_copy(update={"current_hp": new_hp}),
        )
        updated_state = _set_action_count(updated_state, actor_id, state.action_counts[actor_id] - 1)
        return (
            updated_state,
            CheckResult(
                proposal_id=f"check_attack_{attack.id}_{roll_index:06d}",
                roll_result=attack_roll,
                degree=degree,
                effects=effects,
                state_deltas=deltas,
            ),
            damage_roll,
        )

    def move(self, state: CombatState, actor_id: str, new_position: PositionTagValue) -> CombatState:
        """Move a combatant to another first-slice position tag, consuming one action."""

        _find_combatant(state, actor_id)
        _require_actions(state, actor_id)
        if new_position not in _ALLOWED_POSITIONS:
            raise ValueError(f"unsupported position {new_position!r}")
        current_position = state.positions[actor_id]
        if current_position == new_position:
            raise ValueError(f"{actor_id} is already at {current_position}")
        return _set_action_count(
            state.model_copy(update={"positions": {**state.positions, actor_id: new_position}}),
            actor_id,
            state.action_counts[actor_id] - 1,
        )

    def end_turn(self, state: CombatState) -> CombatState:
        """Advance to the next living combatant, resetting their turn resources."""

        living_ids = {combatant.id for combatant in state.combatants if combatant.current_hp > 0}
        if not living_ids:
            return state
        order = [entry.combatant_id for entry in state.initiative_order]
        current_index = order.index(state.active_combatant_id)
        for offset in range(1, len(order) + 1):
            next_index = (current_index + offset) % len(order)
            next_id = order[next_index]
            if next_id in living_ids:
                round_number = state.round_number + (1 if next_index <= current_index else 0)
                return state.model_copy(
                    update={
                        "round_number": round_number,
                        "active_combatant_id": next_id,
                        "action_counts": {**state.action_counts, next_id: 3},
                        "reaction_available": {**state.reaction_available, next_id: True},
                    }
                )
        return state

    def is_encounter_complete(self, state: CombatState) -> bool:
        """Return whether either the PC or all enemies are defeated."""

        pc = state.combatants[0]
        enemies = state.combatants[1:]
        return pc.current_hp == 0 or all(enemy.current_hp == 0 for enemy in enemies)

    def _roll_initiative(
        self,
        sheet: CharacterSheet,
        enemies: tuple[CombatantState, ...],
        *,
        roll_index: int,
    ) -> list[CheckResult]:
        pc_result = self.rules.resolve_check(
            sheet,
            stat="perception",
            dc=10,
            reason="initiative",
            roll_index=roll_index,
            kind="initiative",
        )
        enemy_results = [
            CheckResult(
                proposal_id=f"check_initiative_{enemy.id}_{roll_index + offset:06d}",
                roll_result=self.dice.roll_d20(
                    purpose="initiative",
                    actor_id=enemy.id,
                    modifier=enemy.perception_modifier,
                    roll_index=roll_index + offset,
                    dc=None,
                ),
                degree="success",
                effects=[],
                state_deltas=[],
            )
            for offset, enemy in enumerate(enemies, start=1)
        ]
        return [pc_result, *enemy_results]


def _combatant_from_sheet(sheet: CharacterSheet) -> CombatantState:
    return CombatantState(
        id=sheet.id,
        name=sheet.name,
        level=sheet.level,
        current_hp=sheet.current_hp,
        max_hp=sheet.max_hp,
        armor_class=sheet.armor_class,
        perception_modifier=sheet.perception_modifier,
        attacks=sheet.attacks,
        saving_throws=sheet.saving_throws,
        xp_value=0,
        conditions=sheet.conditions,
    )


def _actor_id_from_roll_id(roll_id: str) -> str:
    for prefix in ("roll_perception_", "roll_initiative_"):
        if roll_id.startswith(prefix):
            return roll_id.removeprefix(prefix).rsplit("_", 1)[0]
    raise ValueError(f"unsupported initiative roll id {roll_id!r}")


def _find_combatant(state: CombatState, combatant_id: str) -> CombatantState:
    for combatant in state.combatants:
        if combatant.id == combatant_id:
            return combatant
    raise ValueError(f"unknown combatant {combatant_id}")


def _find_attack(combatant: CombatantState, attack_id: str) -> AttackProfile:
    for attack in combatant.attacks:
        if attack.id == attack_id:
            return attack
    raise ValueError(f"{combatant.id} has no attack {attack_id}")


def _require_actions(state: CombatState, combatant_id: str) -> None:
    if state.action_counts.get(combatant_id, 0) <= 0:
        raise ValueError(f"No actions remaining for {combatant_id}")


def _damage_die_and_modifier(attack: AttackProfile) -> tuple[str, int]:
    if attack.damage.startswith("1d8+4 "):
        return "d8", 4
    if attack.damage.startswith("1d6 "):
        return "d6", 0
    raise ValueError(f"unsupported first-slice damage expression {attack.damage!r}")


def _replace_combatant(state: CombatState, combatant_id: str, replacement: CombatantState) -> CombatState:
    return state.model_copy(
        update={
            "combatants": [replacement if combatant.id == combatant_id else combatant for combatant in state.combatants]
        }
    )


def _set_action_count(state: CombatState, combatant_id: str, actions: int) -> CombatState:
    return state.model_copy(update={"action_counts": {**state.action_counts, combatant_id: actions}})
