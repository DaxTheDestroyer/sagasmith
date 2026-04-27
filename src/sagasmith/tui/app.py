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
        # Service connection owned by the app for deterministic lifecycle close.
        # Set by runtime.build_app(); None in unit tests that bypass build_app().
        self._service_conn: sqlite3.Connection | None = None

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

    def on_command_invoked(self, event: CommandInvoked) -> None:
        if self.commands is None:
            # Plan 03-03: only /help is wired via runtime registry.
            # Plan 03-04 replaces this guard with full registry dispatch.
            return
        self.commands.dispatch(self, event.name, event.args)

    def on_unmount(self) -> None:
        """Close the long-lived service connection deterministically on TUI exit.

        Without an explicit close, the WAL file is not checkpointed until Python's
        GC finalizes the connection — which is non-deterministic and leaks file
        handles inside test harnesses (run_test()).
        """
        if self._service_conn is not None:
            self._service_conn.close()
            self._service_conn = None
