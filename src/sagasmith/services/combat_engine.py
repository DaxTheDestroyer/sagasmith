"""Deterministic first-slice combat state transitions."""

from __future__ import annotations

from dataclasses import dataclass

from sagasmith.schemas.common import CombatantState, InitiativeEntry
from sagasmith.schemas.mechanics import CharacterSheet, CheckResult, CombatState
from sagasmith.services.dice import DiceService
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
        if any(not isinstance(enemy, CombatantState) for enemy in enemies):
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

        positions = {pc.id: "near"}
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
