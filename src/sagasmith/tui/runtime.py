"""TUIRuntime — constructs a ready-to-run SagaSmithApp from a campaign path."""

from __future__ import annotations

from pathlib import Path

from sagasmith.app.campaign_ref import open_campaign_ref

# Phase 7: warm the NetworkX graph cache on startup
from sagasmith.memory.graph import warm_vault_graph
from sagasmith.onboarding.store import OnboardingStore
from sagasmith.persistence.db import open_campaign_db
from sagasmith.providers.runtime import build_provider_runtime
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
from sagasmith.tui.commands.recovery import DiscardCommand, RetryCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand
from sagasmith.tui.commands.settings import SettingsCommand
from sagasmith.vault import VaultService

SCROLLBACK_LIMIT = 50  # last N transcript entries loaded on resume (TUI-03)


def build_app(campaign_root: Path, *, build_graph_runtime: bool = True) -> SagaSmithApp:
    """Open a campaign and return a ready-to-run SagaSmithApp.

    Caller is responsible for ``.run()`` (blocking TUI) or ``.run_test()``
    (async test harness).

    Raises ValueError if the campaign layout is invalid (exits CLI with code 2).

    Note: ``service_conn`` is a single long-lived SQLite connection owned by the app.
    Textual's event loop is single-threaded so SQLite's thread-safety warnings don't
    apply. For Phase 3 scope this is acceptable; Phase 4 graph runtime will revisit
    connection management when checkpointing runs concurrently with UI.
    """
    opened = open_campaign_ref(campaign_root)
    paths = opened.paths
    manifest = opened.manifest
    app = SagaSmithApp(paths=paths, manifest=manifest)

    # Long-lived connection for service bindings (TUI owns its lifetime).
    service_conn = open_campaign_db(paths.db, read_only=False)
    app.bind_service_connection(service_conn)
    app.onboarding_store = OnboardingStore(conn=service_conn)
    app.safety_events = SafetyEventService(conn=service_conn)

    # CostGovernor: load session budget from onboarding if present, else 0 (unlimited-for-dev).
    session_budget = 0.0
    triple = app.onboarding_store.reload(manifest.campaign_id)
    if triple is not None:
        session_budget = triple.player_profile.budget.per_session_usd
    app.cost_governor = CostGovernor(session_budget_usd=session_budget)

    next_session_number = _next_session_number(service_conn, manifest.campaign_id)
    app.current_session_id = f"session_{next_session_number:03d}"
    app.current_session_number = next_session_number

    # Phase 4: wire GraphRuntime into the TUI app.
    if build_graph_runtime:
        from sagasmith.graph.bootstrap import GraphBootstrap
        from sagasmith.graph.runtime import build_persistent_graph
        from sagasmith.services.dice import DiceService

        dice_service = DiceService(
            campaign_seed=manifest.campaign_id,
            session_seed=app.current_session_id,
        )
        vault_service = VaultService(
            campaign_id=manifest.campaign_id, player_vault_root=paths.player_vault
        )
        # Phase 7: warm the NetworkX graph cache from master vault
        warm_vault_graph(vault_service.master_path)
        provider_result = build_provider_runtime(service_conn, manifest.campaign_id)
        if provider_result.error is not None or provider_result.runtime is None:
            service_conn.close()
            error = provider_result.error
            message = error.message if error is not None else "Provider Runtime unavailable."
            raise ValueError(message)
        bootstrap = GraphBootstrap.from_services(
            dice=dice_service,
            cost=app.cost_governor,
            safety=app.safety_events,
            llm=provider_result.runtime.client,
            provider_config=provider_result.runtime.config,
            vault_service=vault_service,
        )
        app.graph_runtime = build_persistent_graph(
            bootstrap, service_conn, campaign_id=manifest.campaign_id
        )

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
        RetryCommand(),
        DiscardCommand(),
    ]:
        registry.register(cmd)
    app.commands = registry

    # Load recent transcript for scrollback (TUI-03).
    app.initial_scrollback = _load_scrollback(paths.db, campaign_id=manifest.campaign_id)
    return app


def _next_session_number(conn, campaign_id: str) -> int:  # type: ignore[no-untyped-def]
    """Return next numeric session number for a resumed campaign."""
    from sagasmith.persistence.turn_history import CanonicalTurnHistory

    session_ids = CanonicalTurnHistory(conn).session_ids_for_campaign(campaign_id)
    max_num = 0
    for session_id in session_ids:
        prefix, sep, suffix = session_id.rpartition("_")
        if sep and prefix == "session" and suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return max_num + 1 if max_num else 1


def _load_scrollback(db_path: Path, *, campaign_id: str) -> list[str]:
    """Return last SCROLLBACK_LIMIT rendered canonical transcript lines.

    Rendering rule:
      - kind='player_input'    → f"> {content}"
      - kind='narration_final' → content (verbatim)
      - kind='system_note'     → f"[{content}]"  (T-03-18: unknown kinds also wrap here)

    Uses a read-only connection; closes it before returning.
    """
    from sagasmith.persistence.turn_history import CanonicalTurnHistory

    conn = open_campaign_db(db_path, read_only=True)
    try:
        entries = CanonicalTurnHistory(conn).scrollback(campaign_id, limit=SCROLLBACK_LIMIT)
    finally:
        conn.close()
    lines: list[str] = []
    for entry in entries:
        if entry.kind == "player_input":
            lines.append(f"> {entry.content}")
        elif entry.kind == "narration_final":
            lines.append(entry.content)
        else:
            # T-03-18: unknown kinds render as system notes wrapped in [...]
            lines.append(f"[{entry.content}]")
    return lines
