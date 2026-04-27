"""Control command implementations: save, recap, sheet, inventory, map, clock, budget, retcon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp

from sagasmith.tui.widgets.narration import NarrationArea


def _write(app: SagaSmithApp, line: str) -> None:
    app.query_one(NarrationArea).append_line(line)


@dataclass(frozen=True)
class SaveCommand:
    name: str = "save"
    description: str = "Manually save current turn state."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        _write(
            app,
            "[system] /save (stub — wired in Phase 4 graph runtime; auto-save is already on per HouseRules).",
        )


@dataclass(frozen=True)
class RecapCommand:
    name: str = "recap"
    description: str = "Show rolling summary of recent events."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        _write(app, "[system] /recap (stub — Phase 7 Archivist will assemble real summaries).")


@dataclass(frozen=True)
class SheetCommand:
    name: str = "sheet"
    description: str = "Show character sheet."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        snap = app.state.status
        hp = snap.format_hp()
        _write(
            app,
            f"[system] /sheet (stub — Phase 5 PF2e vertical slice wires the full CharacterSheet). Current: {hp}.",
        )


@dataclass(frozen=True)
class InventoryCommand:
    name: str = "inventory"
    description: str = "Show inventory."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        _write(
            app,
            "[system] /inventory (stub — Phase 5 PF2e vertical slice will render inventory from CharacterSheet).",
        )


@dataclass(frozen=True)
class MapCommand:
    name: str = "map"
    description: str = "Show current location and theater-of-mind positions."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        snap = app.state.status
        loc = snap.location or "unknown"
        _write(
            app,
            f"[system] /map: {loc} (position tags: close/near/far/behind_cover — Phase 5 wires combat positions).",
        )


@dataclass(frozen=True)
class ClockCommand:
    name: str = "clock"
    description: str = "Show in-game clock."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        _write(app, f"[system] {app.state.status.format_clock()}.")


@dataclass(frozen=True)
class BudgetCommand:
    name: str = "budget"
    description: str = "Show session budget usage (COST-05)."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        governor = app.cost_governor
        if governor is None:
            _write(app, "[system] /budget: no session governor active (no paid calls yet).")
            return
        inspection = governor.format_budget_inspection()
        line = (
            f"Budget ${inspection.session_budget_usd:.2f}: "
            f"spent ${inspection.spent_usd_estimate:.4f} "
            f"({inspection.fraction_used * 100:.0f}%), "
            f"remaining ${inspection.remaining_usd:.4f}, "
            f"tokens {inspection.tokens_total}, "
            f"warnings_sent={list(inspection.warnings_sent)}, "
            f"hard_stopped={inspection.hard_stopped}"
        )
        _write(app, f"[system] /budget: {line}")


@dataclass(frozen=True)
class RetconCommand:
    name: str = "retcon"
    description: str = "Retcon the last completed turn (confirmation required)."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        # Phase 4 acknowledge-only: 04-REVIEWS.md Claude review suggests RETCON
        # should not interrupt today. Phase 8 will wire the full confirmation +
        # rollback flow. No InterruptKind.RETCON posted here.
        _write(
            app,
            "[system] /retcon (stub — Phase 8 release-hardening wires the retcon pipeline; confirmation flow will be added there).",
        )
