"""Control command implementations: save, recap, sheet, inventory, map, clock, budget, retcon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from sagasmith.rules.first_slice import make_first_slice_character
from sagasmith.schemas.mechanics import CharacterSheet
from sagasmith.persistence.repositories import TranscriptRepository

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp

from sagasmith.tui.widgets.narration import NarrationArea
from sagasmith.tui.widgets.sheet import render_character_sheet


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
        values: dict[str, object] = {}
        if app.graph_runtime is not None:
            snapshot = app.graph_runtime.graph.get_state(app.graph_runtime.thread_config)
            values = dict(getattr(snapshot, "values", {}) or {})
        summary = values.get("rolling_summary") if values else None
        if not isinstance(summary, str) or not summary.strip():
            summary = "[No summary available]"

        _write(app, "=== RECAP ===")
        for line in summary.splitlines() or [summary]:
            _write(app, line)

        conn = getattr(app, "_service_conn", None)
        if conn is None:
            return
        entries = TranscriptRepository(conn).list_recent(limit=5)
        if entries:
            _write(app, "--- Recent transcript ---")
        for entry in entries:
            if entry.kind == "player_input":
                _write(app, f"> {entry.content}")
            elif entry.kind == "narration_final":
                _write(app, entry.content)
            else:
                _write(app, f"[{entry.content}]")


@dataclass(frozen=True)
class SheetCommand:
    name: str = "sheet"
    description: str = "Show character sheet."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        sheet = _resolve_character_sheet(app)
        for line in render_character_sheet(sheet).splitlines():
            _write(app, line)


def _resolve_character_sheet(app: SagaSmithApp) -> CharacterSheet:
    if app.graph_runtime is not None:
        snapshot = app.graph_runtime.graph.get_state(app.graph_runtime.thread_config)
        values = getattr(snapshot, "values", {}) or {}
        live_sheet = values.get("character_sheet")
        if live_sheet is not None:
            try:
                return CharacterSheet.model_validate(live_sheet)
            except ValidationError:
                pass
    return make_first_slice_character()


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
        if app.graph_runtime is not None:
            from sagasmith.graph.interrupts import InterruptKind

            app.graph_runtime.post_interrupt(
                kind=InterruptKind.RETCON,
                payload={"reason": "player typed /retcon"},
            )
        _write(
            app,
            "[system] /retcon requested. Phase 8 release-hardening wires confirmation and rollback.",
        )
