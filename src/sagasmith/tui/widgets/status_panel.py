"""StatusPanel widget — renders a StatusSnapshot dataclass."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from sagasmith.schemas.mechanics import CombatState
from sagasmith.tui.state import StatusSnapshot


def format_combat_status(combat_state: CombatState | None) -> list[str]:
    """Format deterministic combat state as plain status-panel text."""

    if combat_state is None:
        return ["Combat: —"]

    active_id = combat_state.active_combatant_id
    combatants_by_id = {combatant.id: combatant for combatant in combat_state.combatants}
    active = combatants_by_id.get(active_id)
    defeated_suffix = " (defeated)" if active is not None and active.current_hp == 0 else ""
    remaining_actions = combat_state.action_counts.get(active_id, 0)
    reaction = "available" if combat_state.reaction_available.get(active_id, False) else "spent"
    positions = ", ".join(
        f"{combatant_id}={position}" for combatant_id, position in sorted(combat_state.positions.items())
    )
    enemies = [combatant for combatant in combat_state.combatants if combatant.id != "pc"]
    if not enemies:
        enemy_line = "Enemies: none"
    else:
        rendered_enemies = [
            f"{enemy.id} HP {enemy.current_hp}/{enemy.max_hp}" for enemy in enemies[:2]
        ]
        enemy_line = "Enemies: " + "; ".join(rendered_enemies)

    return [
        f"Round: {combat_state.round_number}",
        f"Active combatant: {active_id}{defeated_suffix}",
        f"Actions: {remaining_actions}/3 for {active_id}",
        f"Reaction: {reaction}",
        f"Positions: {positions or '—'}",
        enemy_line,
    ]


def format_status_snapshot(snapshot: StatusSnapshot) -> str:
    """Format the full status snapshot for tests and the Textual widget."""

    lines = [
        snapshot.format_hp(),
        "Conditions: " + (", ".join(snapshot.conditions) if snapshot.conditions else "—"),
        f"Quest: {snapshot.active_quest or '—'}",
        f"Location: {snapshot.location or '—'}",
        snapshot.format_clock(),
        "Last rolls:",
        *[f"  {roll}" for roll in (snapshot.last_rolls or ("—",))[:3]],
        *format_combat_status(snapshot.combat_state),
    ]
    if snapshot.vault_sync_warning:
        lines.extend(["", f"VAULT SYNC WARNING: {snapshot.vault_sync_warning}"])
    return "\n".join(lines)


class StatusPanel(Widget):
    """Right-side status panel showing HP, conditions, quest, location, clock, and last rolls."""

    DEFAULT_CSS = """
    StatusPanel { width: 32; border: solid $accent; padding: 1; }
    """

    snapshot: reactive[StatusSnapshot] = reactive(StatusSnapshot(), always_update=True)

    def compose(self):  # type: ignore[override]
        yield Static(id="status-body")

    def watch_snapshot(self, new: StatusSnapshot) -> None:
        body = self.query_one("#status-body", Static)
        body.update(self._format_snapshot(new))

    def _format_snapshot(self, s: StatusSnapshot) -> str:
        return format_status_snapshot(s)
