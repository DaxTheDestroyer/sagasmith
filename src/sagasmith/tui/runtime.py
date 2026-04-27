"""TUIRuntime — constructs a ready-to-run SagaSmithApp from a campaign path."""

from __future__ import annotations

from pathlib import Path

from sagasmith.app.campaign import open_campaign
from sagasmith.onboarding.store import OnboardingStore
from sagasmith.persistence.db import open_campaign_db
from sagasmith.services.cost import CostGovernor
from sagasmith.services.safety import SafetyEventService
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import (
    BudgetCommand,
    ClockCommand,
    InventoryCommand,
    MapCommand,
    RecapCommand,
    RetconCommand,
    SaveCommand,
    SheetCommand,
)
from sagasmith.tui.commands.help import HelpCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand
from sagasmith.tui.commands.settings import SettingsCommand

SCROLLBACK_LIMIT = 50  # last N transcript entries loaded on resume (TUI-03)


def build_app(campaign_root: Path) -> SagaSmithApp:
    """Open a campaign and return a ready-to-run SagaSmithApp.

    Caller is responsible for ``.run()`` (blocking TUI) or ``.run_test()``
    (async test harness).

    Raises ValueError if the campaign layout is invalid (exits CLI with code 2).

    Note: ``service_conn`` is a single long-lived SQLite connection owned by the app.
    Textual's event loop is single-threaded so SQLite's thread-safety warnings don't
    apply. For Phase 3 scope this is acceptable; Phase 4 graph runtime will revisit
    connection management when checkpointing runs concurrently with UI.
    """
    paths, manifest = open_campaign(campaign_root)
    app = SagaSmithApp(paths=paths, manifest=manifest)

    # Long-lived connection for service bindings (TUI owns its lifetime).
    service_conn = open_campaign_db(paths.db, read_only=False)
    app._service_conn = service_conn  # owned by app; closed in on_unmount()
    app.onboarding_store = OnboardingStore(conn=service_conn)
    app.safety_events = SafetyEventService(conn=service_conn)

    # CostGovernor: load session budget from onboarding if present, else 0 (unlimited-for-dev).
    session_budget = 0.0
    triple = app.onboarding_store.reload(manifest.campaign_id)
    if triple is not None:
        session_budget = triple.player_profile.budget.per_session_usd
    app.cost_governor = CostGovernor(session_budget_usd=session_budget)

    registry = CommandRegistry()
    registry.register(HelpCommand(registry=registry))
    for cmd in [
        SaveCommand(),
        RecapCommand(),
        SheetCommand(),
        InventoryCommand(),
        MapCommand(),
        ClockCommand(),
        BudgetCommand(),
        PauseCommand(),
        LineCommand(),
        RetconCommand(),
        SettingsCommand(),
    ]:
        registry.register(cmd)
    app.commands = registry  # type: ignore[assignment]

    # Load recent transcript for scrollback (TUI-03).
    app.initial_scrollback = _load_scrollback(paths.db)
    return app


def _load_scrollback(db_path: Path) -> list[str]:
    """Return last SCROLLBACK_LIMIT rendered lines from transcript_entries.

    Rendering rule:
      - kind='player_input'    → f"> {content}"
      - kind='narration_final' → content (verbatim)
      - kind='system_note'     → f"[{content}]"  (T-03-18: unknown kinds also wrap here)

    Uses a read-only connection; closes it before returning.
    """
    lines: list[str] = []
    conn = open_campaign_db(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT kind, content
              FROM transcript_entries
             ORDER BY id DESC
             LIMIT ?
            """,
            (SCROLLBACK_LIMIT,),
        ).fetchall()
    finally:
        conn.close()
    # Rows are newest-first; reverse for chronological display.
    for kind, content in reversed(rows):
        if kind == "player_input":
            lines.append(f"> {content}")
        elif kind == "narration_final":
            lines.append(content)
        else:
            # T-03-18: unknown kinds render as system notes wrapped in [...]
            lines.append(f"[{content}]")
    return lines
