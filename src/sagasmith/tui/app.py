"""SagaSmithApp \u2014 the root Textual application for the TUI shell."""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message

from sagasmith.app.paths import CampaignPaths
from sagasmith.schemas.campaign import CampaignManifest
from sagasmith.tui.state import StatusSnapshot, TUIState
from sagasmith.tui.widgets.input_line import InputLine
from sagasmith.tui.widgets.narration import NarrationArea
from sagasmith.tui.widgets.safety_bar import SafetyBar
from sagasmith.tui.widgets.status_panel import StatusPanel

if TYPE_CHECKING:
    from sagasmith.graph.runtime import GraphRuntime
    from sagasmith.onboarding.store import OnboardingStore
    from sagasmith.services.cost import CostGovernor
    from sagasmith.services.safety import SafetyEventService
    from sagasmith.tui.commands.registry import CommandRegistry


class PlayerInputSubmitted(Message):
    """Free-text input was submitted (no leading /)."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class CommandInvoked(Message):
    """Slash command was submitted (leading /; text is the part AFTER the /)."""

    def __init__(self, raw: str, name: str, args: tuple[str, ...]) -> None:
        self.raw = raw
        self.name = name
        self.args = args
        super().__init__()


class SagaSmithApp(App):  # type: ignore[type-arg]
    """Root Textual application. Wired by TUIRuntime.build_app()."""

    CSS = """
    #main-row { height: 1fr; }
    """
    BINDINGS: ClassVar = [  # type: ignore[assignment]
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, paths: CampaignPaths, manifest: CampaignManifest) -> None:
        super().__init__()
        self.paths = paths
        self.manifest = manifest
        self.state = TUIState()
        # Set by runtime.build_app() BEFORE mount. Empty list if fresh campaign.
        self.initial_scrollback: list[str] = []
        # registry is assigned by runtime.build_app BEFORE mount (Plan 03-03).
        # Plan 03-04 replaces None-guard with full registry dispatch.
        self.commands: CommandRegistry | None = None
        # Runtime-scoped services set by build_app (Plan 03-04).
        # Explicitly typed | None so unit tests can construct apps without services.
        self.onboarding_store: OnboardingStore | None = None
        self.safety_events: SafetyEventService | None = None
        self.cost_governor: CostGovernor | None = None
        # Phase 4: graph runtime bound by build_app when graph is compiled.
        # None in headless CLI tests or when build_graph_runtime=False.
        self.graph_runtime: GraphRuntime | None = None
        # Turn/session tracking (set by runtime or tests before input).
        self.current_turn_id: str | None = None
        self.current_session_id: str = "session_001"
        self.current_session_number: int = 1
        self._last_synced_graph_turn_id: str | None = None
        self._synced_graph_narration_count = 0
        self._synced_graph_check_result_count = 0
        # Service connection owned by the app for deterministic lifecycle close.
        # Set by runtime.build_app(); None in unit tests that bypass build_app().
        self._service_conn: sqlite3.Connection | None = None

    @property
    def narration(self) -> NarrationArea:
        return self.query_one(NarrationArea)

    def bind_service_connection(self, conn: sqlite3.Connection) -> None:
        """Bind the runtime-owned SQLite service connection to the app lifecycle."""
        self._service_conn = conn

    def compose(self) -> ComposeResult:
        yield SafetyBar()
        with Horizontal(id="main-row"):
            yield NarrationArea(id="narration-area")
            yield StatusPanel(id="status-panel")
        yield InputLine(id="input-line")

    def on_mount(self) -> None:
        narration = self.query_one(NarrationArea)
        # Load persisted scrollback first (TUI-03), then welcome lines.
        initial = getattr(self, "initial_scrollback", []) or []
        if initial:
            for line in initial:
                narration.append_line(line)
            narration.append_line("\u2014 resumed \u2014")
        narration.append_line(f"Campaign: {self.manifest.campaign_name}")
        narration.append_line("Type /help for commands, or describe what your character does.")
        status = self.query_one(StatusPanel)
        status.snapshot = self.state.status  # triggers watcher

    def on_input_line_submitted(self, event: InputLine.Submitted) -> None:
        raw = event.raw
        if raw.startswith("/"):
            body = raw[1:]
            tokens = body.split()
            if not tokens:
                return
            name, *rest = tokens
            self.post_message(CommandInvoked(raw=raw, name=name, args=tuple(rest)))
        else:
            self.post_message(PlayerInputSubmitted(text=raw))

    def on_player_input_submitted(self, event: PlayerInputSubmitted) -> None:
        narration = self.query_one(NarrationArea)
        narration.append_line(f"> {event.text}")
        self.state.scrollback.append(f"> {event.text}")
        # Phase 4: drive graph turn when runtime is bound
        if self.graph_runtime is not None:
            snapshot = self.graph_runtime.graph.get_state(self.graph_runtime.thread_config)
            if snapshot.next == ("orator",):
                self.graph_runtime.graph.invoke(None, self.graph_runtime.thread_config)
                snapshot = self.graph_runtime.graph.get_state(self.graph_runtime.thread_config)
            if snapshot.values:
                self.current_turn_id = _next_turn_id(
                    str(snapshot.values.get("turn_id") or self.current_turn_id or "turn_000000")
                )
            current_values = dict(getattr(snapshot, "values", {}) or {})
            state = self._build_play_state(event.text, current_values or None)
            self.graph_runtime.invoke_turn(state)
            self._sync_mechanics_from_graph()
            self._sync_vault_warning_from_latest_turn()

    def _build_play_state(
        self,
        player_input: str,
        current_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Minimal play-phase state for stub graph nodes."""
        from sagasmith.rules.first_slice import make_first_slice_character

        budget = 0.0
        if self.cost_governor is not None:
            budget = self.cost_governor.state.session_budget_usd
        existing_sheet = None if current_state is None else current_state.get("character_sheet")
        existing_combat = None if current_state is None else current_state.get("combat_state")
        existing_checks = [] if current_state is None else current_state.get("check_results", [])
        existing_deltas = [] if current_state is None else current_state.get("state_deltas", [])
        existing_narration = (
            [] if current_state is None else current_state.get("pending_narration", [])
        )
        phase = "combat" if existing_combat is not None else "play"
        return {
            "campaign_id": self.manifest.campaign_id,
            "session_id": self.current_session_id,
            "turn_id": self.current_turn_id or "turn_000001",
            "phase": phase,
            "player_profile": None,
            "content_policy": None,
            "house_rules": None,
            "character_sheet": existing_sheet
            if existing_sheet is not None
            else make_first_slice_character().model_dump(),
            "session_state": {
                "current_scene_id": None,
                "current_location_id": None,
                "active_quest_ids": [],
                "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
                "turn_count": 0,
                "transcript_cursor": None,
                "last_checkpoint_id": None,
                "session_number": self.current_session_number,
            },
            "combat_state": existing_combat,
            "pending_player_input": player_input,
            "memory_packet": None,
            "scene_brief": None,
            "check_results": existing_checks,
            "state_deltas": existing_deltas,
            "pending_conflicts": [],
            "pending_narration": existing_narration,
            "safety_events": [],
            "cost_state": {
                "session_budget_usd": budget,
                "spent_usd_estimate": 0.0,
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "unknown_cost_call_count": 0,
                "warnings_sent": [],
                "hard_stopped": False,
            },
            "last_interrupt": None,
        }

    def on_command_invoked(self, event: CommandInvoked) -> None:
        if self.commands is None:
            # Plan 03-03: only /help is wired via runtime registry.
            # Plan 03-04 replaces this guard with full registry dispatch.
            return
        self.commands.dispatch(self, event.name, event.args)

    async def action_quit(self) -> None:
        """Record session-end intent before Textual exits."""
        if self.graph_runtime is not None:
            from sagasmith.graph.interrupts import InterruptKind

            self.graph_runtime.post_interrupt(
                kind=InterruptKind.SESSION_END,
                payload={"reason": "player quit"},
            )
        self.exit()

    def _sync_narration_from_graph(self) -> None:
        """Append any new pending_narration lines from graph state to the TUI."""
        if self.graph_runtime is None:
            return
        snapshot = self.graph_runtime.graph.get_state(self.graph_runtime.thread_config)
        values = getattr(snapshot, "values", {}) or {}
        turn_id = values.get("turn_id")
        if turn_id != self._last_synced_graph_turn_id:
            self._last_synced_graph_turn_id = turn_id
            self._synced_graph_narration_count = 0
            self._synced_graph_check_result_count = 0
        pending = values.get("pending_narration", [])
        if pending and len(pending) > self._synced_graph_narration_count:
            narration = self.query_one(NarrationArea)
            for line in pending[self._synced_graph_narration_count :]:
                narration.append_line(line)
            self._synced_graph_narration_count = len(pending)

    def sync_narration_from_graph(self) -> None:
        """Public wrapper for command handlers that need to refresh narration."""
        self._sync_narration_from_graph()

    def _sync_mechanics_from_graph(self) -> None:
        """Render newly resolved mechanics and refresh status from graph state."""
        if self.graph_runtime is None:
            return

        from pydantic import ValidationError

        from sagasmith.schemas.mechanics import CharacterSheet, CheckResult, CombatState
        from sagasmith.tui.state import StatusSnapshot
        from sagasmith.tui.widgets.dice_overlay import render_compact_roll_line, render_reveal_check

        self._sync_narration_from_graph()
        snapshot = self.graph_runtime.graph.get_state(self.graph_runtime.thread_config)
        values = getattr(snapshot, "values", {}) or {}
        turn_id = values.get("turn_id")
        if turn_id != self._last_synced_graph_turn_id:
            self._last_synced_graph_turn_id = turn_id
            self._synced_graph_narration_count = 0
            self._synced_graph_check_result_count = 0

        raw_results = values.get("check_results", []) or []
        check_results: list[CheckResult] = []
        for raw in raw_results:
            try:
                check_results.append(CheckResult.model_validate(raw))
            except ValidationError:
                continue

        narration = self.query_one(NarrationArea)
        for result in check_results[self._synced_graph_check_result_count :]:
            reason = result.proposal_id
            narration.append_line(f"CheckResult: {result.proposal_id}")
            narration.append_line(render_compact_roll_line(result, reason=reason))
            narration.append_line(render_reveal_check(result, reason=reason))
            for effect in result.effects:
                narration.append_line(effect.description)
        self._synced_graph_check_result_count = len(check_results)

        combat_state: CombatState | None = None
        if values.get("combat_state") is not None:
            try:
                combat_state = CombatState.model_validate(values["combat_state"])
            except ValidationError:
                combat_state = None

        hp_current = None
        hp_max = None
        if combat_state is not None:
            pc = next(
                (
                    combatant
                    for combatant in combat_state.combatants
                    if combatant.id.startswith("pc_")
                ),
                None,
            )
            if pc is not None:
                hp_current = pc.current_hp
                hp_max = pc.max_hp
        elif values.get("character_sheet") is not None:
            try:
                sheet = CharacterSheet.model_validate(values["character_sheet"])
                hp_current = sheet.current_hp
                hp_max = sheet.max_hp
            except ValidationError:
                pass

        last_rolls = tuple(
            render_compact_roll_line(result, reason=result.proposal_id)
            for result in check_results[-3:]
        )
        self.state.status = StatusSnapshot(
            hp_current=hp_current,
            hp_max=hp_max,
            last_rolls=last_rolls,
            combat_state=combat_state,
            vault_sync_warning=self.state.vault_sync_warning,
        )
        with suppress(Exception):
            self.query_one(StatusPanel).snapshot = self.state.status

    def _sync_vault_warning_from_latest_turn(self) -> None:
        """Surface latest persistent vault sync warning in the status panel."""
        if self._service_conn is None:
            return
        from sagasmith.persistence.turn_history import CanonicalTurnHistory

        warning = CanonicalTurnHistory(self._service_conn).latest_sync_warning(
            self.manifest.campaign_id, self.current_session_id
        )
        self.state.vault_sync_warning = warning
        self.state.status = StatusSnapshot(
            hp_current=self.state.status.hp_current,
            hp_max=self.state.status.hp_max,
            conditions=self.state.status.conditions,
            active_quest=self.state.status.active_quest,
            location=self.state.status.location,
            clock_day=self.state.status.clock_day,
            clock_hhmm=self.state.status.clock_hhmm,
            last_rolls=self.state.status.last_rolls,
            combat_state=self.state.status.combat_state,
            vault_sync_warning=warning,
        )
        with suppress(Exception):
            self.query_one(StatusPanel).snapshot = self.state.status

    def sync_after_retcon(self) -> None:
        """Resync narration and mechanics after a retcon rewinds graph state.

        Called by RetconCommand after a successful confirm_retcon. Uses
        suppress blocks so a transient TUI sync failure after retcon does not
        crash the app — the state is already correct in the graph.
        """
        with suppress(Exception):
            self._sync_narration_from_graph()
        with suppress(Exception):
            self._sync_mechanics_from_graph()
        with suppress(Exception):
            self._sync_vault_warning_from_latest_turn()

    def on_unmount(self) -> None:
        """Close the long-lived service connection deterministically on TUI exit.

        Without an explicit close, the WAL file is not checkpointed until Python's
        GC finalizes the connection — which is non-deterministic and leaks file
        handles inside test harnesses (run_test()).
        """
        if self._service_conn is not None:
            self._service_conn.close()
            self._service_conn = None


def _next_turn_id(turn_id: str) -> str:
    prefix, sep, suffix = turn_id.rpartition("_")
    if sep and suffix.isdigit():
        return f"{prefix}_{int(suffix) + 1:0{len(suffix)}d}"
    return f"{turn_id}_next"
