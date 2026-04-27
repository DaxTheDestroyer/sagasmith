"""SagaSmithApp \u2014 the root Textual application for the TUI shell."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message

from sagasmith.app.paths import CampaignPaths
from sagasmith.schemas.campaign import CampaignManifest
from sagasmith.tui.state import TUIState
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
        self._last_synced_graph_turn_id: str | None = None
        self._synced_graph_narration_count = 0
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
            state = self._build_play_state(event.text)
            self.graph_runtime.invoke_turn(state)

    def _build_play_state(self, player_input: str) -> dict[str, object]:
        """Minimal play-phase state for stub graph nodes."""
        budget = 0.0
        if self.cost_governor is not None:
            budget = self.cost_governor.state.session_budget_usd
        return {
            "campaign_id": self.manifest.campaign_id,
            "session_id": self.current_session_id,
            "turn_id": self.current_turn_id or "turn_000001",
            "phase": "play",
            "player_profile": None,
            "content_policy": None,
            "house_rules": None,
            "character_sheet": None,
            "session_state": {
                "current_scene_id": None,
                "current_location_id": None,
                "active_quest_ids": [],
                "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
                "turn_count": 0,
                "transcript_cursor": None,
                "last_checkpoint_id": None,
            },
            "combat_state": None,
            "pending_player_input": player_input,
            "memory_packet": None,
            "scene_brief": None,
            "check_results": [],
            "state_deltas": [],
            "pending_conflicts": [],
            "pending_narration": [],
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
        pending = values.get("pending_narration", [])
        if pending and len(pending) > self._synced_graph_narration_count:
            narration = self.query_one(NarrationArea)
            for line in pending[self._synced_graph_narration_count:]:
                narration.append_line(line)
            self._synced_graph_narration_count = len(pending)

    def on_unmount(self) -> None:
        """Close the long-lived service connection deterministically on TUI exit.

        Without an explicit close, the WAL file is not checkpointed until Python's
        GC finalizes the connection — which is non-deterministic and leaks file
        handles inside test harnesses (run_test()).
        """
        if self._service_conn is not None:
            self._service_conn.close()
            self._service_conn = None
