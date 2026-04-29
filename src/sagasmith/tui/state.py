"""Pure data models for the TUI layer (no Textual imports)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sagasmith.schemas.mechanics import CombatState


@dataclass(frozen=True)
class StatusSnapshot:
    """Read-only snapshot of game state rendered by StatusPanel."""

    hp_current: int | None = None
    hp_max: int | None = None
    conditions: tuple[str, ...] = ()
    active_quest: str | None = None
    location: str | None = None
    clock_day: int | None = None
    clock_hhmm: str | None = None  # "HH:MM"
    last_rolls: tuple[str, ...] = ()  # up to 3 short strings
    combat_state: CombatState | None = None
    vault_sync_warning: str | None = None

    def format_hp(self) -> str:
        if self.hp_current is None or self.hp_max is None:
            return "HP: \u2014"
        return f"HP: {self.hp_current}/{self.hp_max}"

    def format_clock(self) -> str:
        if self.clock_day is None or self.clock_hhmm is None:
            return "Clock: \u2014"
        return f"Day {self.clock_day}, {self.clock_hhmm}"


@dataclass
class TUIState:
    """Mutable UI state \u2014 NOT the graph SagaState. Plan 04 will bridge."""

    status: StatusSnapshot = field(default_factory=StatusSnapshot)
    scrollback: list[str] = field(default_factory=lambda: [])  # rendered transcript lines
    vault_sync_warning: str | None = None
