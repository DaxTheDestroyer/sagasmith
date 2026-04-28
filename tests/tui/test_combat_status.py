"""Tests for Phase 5 combat-aware status panel rendering."""

from __future__ import annotations

from sagasmith.schemas.common import CombatantState, InitiativeEntry
from sagasmith.schemas.mechanics import CombatState
from sagasmith.tui.state import StatusSnapshot
from sagasmith.tui.widgets.status_panel import StatusPanel, format_combat_status


def _combat_state(*, active_id: str = "pc", pc_hp: int = 20, enemies: int = 2) -> CombatState:
    combatants = [
        CombatantState(id="pc", name="Valeros", current_hp=pc_hp, max_hp=20, armor_class=18),
    ]
    if enemies >= 1:
        combatants.append(
            CombatantState(
                id="enemy_weak_melee",
                name="Weak Melee Foe",
                current_hp=8,
                max_hp=8,
                armor_class=15,
            )
        )
    if enemies >= 2:
        combatants.append(
            CombatantState(
                id="enemy_weak_ranged",
                name="Weak Ranged Foe",
                current_hp=6,
                max_hp=6,
                armor_class=14,
            )
        )
    return CombatState(
        encounter_id="encounter_001",
        round_number=2,
        active_combatant_id=active_id,
        initiative_order=[InitiativeEntry(combatant_id=c.id, initiative=15 - index) for index, c in enumerate(combatants)],
        combatants=combatants,
        positions={c.id: "close" for c in combatants},
        action_counts={c.id: 3 for c in combatants},
        reaction_available={c.id: True for c in combatants},
    )


def test_format_combat_status_includes_actions_reaction_positions_and_two_enemies() -> None:
    lines = format_combat_status(_combat_state())
    text = "\n".join(lines)

    assert "Round: 2" in text
    assert "Active combatant: pc" in text
    assert "Actions: 3/3 for pc" in text
    assert "Reaction: available" in text
    assert "Positions:" in text
    assert "pc=close" in text
    assert "Enemies: enemy_weak_melee HP 8/8; enemy_weak_ranged HP 6/6" in text


def test_format_combat_status_handles_zero_and_one_enemy_cases() -> None:
    assert "Enemies: none" in format_combat_status(_combat_state(enemies=0))
    assert "Enemies: enemy_weak_melee HP 8/8" in format_combat_status(_combat_state(enemies=1))


def test_format_combat_status_marks_defeated_active_combatant_and_spent_reaction() -> None:
    combat = _combat_state(active_id="pc", pc_hp=0)
    combat.reaction_available["pc"] = False

    lines = format_combat_status(combat)
    text = "\n".join(lines)

    assert "Active combatant: pc (defeated)" in text
    assert "Reaction: spent" in text


def test_status_panel_limits_last_rolls_and_appends_combat_lines() -> None:
    snapshot = StatusSnapshot(
        last_rolls=(
            "roll one — success (roll_1)",
            "roll two — failure (roll_2)",
            "roll three — critical_success (roll_3)",
            "roll four — critical_failure (roll_4)",
        ),
        combat_state=_combat_state(),
    )

    text = StatusPanel()._format_snapshot(snapshot)

    assert text.count("roll ") == 3
    assert "roll four" not in text
    assert "Last rolls:" in text
    assert "Round: 2" in text
    assert "Actions: 3/3" in text
    assert "Reaction: available" in text
