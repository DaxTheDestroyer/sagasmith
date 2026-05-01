"""CLI command: ``sagasmith play`` - resume an existing campaign. CLI-03."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def play_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c", help="Campaign directory path.")],
    headless_status: Annotated[
        bool,
        typer.Option(
            "--headless-status",
            help="Skip TUI and just print the resume status line (used by Plan 03-01 tests).",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Resume a campaign in the Textual TUI. CLI-03.

    ``--headless-status`` preserves the Plan 03-01 test contract: prints a
    single status line and exits 0 without launching Textual. CI/tests use
    this flag to avoid requiring a TTY.
    """
    if headless_status:
        _print_status_line(campaign)
        return

    # Launch the Textual TUI.
    from sagasmith.tui.runtime import build_app

    try:
        app = build_app(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None
    app.run()


def _print_status_line(campaign: Path) -> None:
    """Print the resume status line and exit. Preserves Plan 03-01 test contract."""
    from sagasmith.app.campaign_ref import open_campaign_ref
    from sagasmith.persistence.db import open_campaign_db

    try:
        opened = open_campaign_ref(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None
    paths = opened.paths
    manifest = opened.manifest

    conn = open_campaign_db(paths.db, read_only=True)
    try:
        from sagasmith.persistence.turn_history import CanonicalTurnHistory

        history = CanonicalTurnHistory(conn)
        last_turn = history.latest_turn_id(manifest.campaign_id) or "none"
        latest_session = history.latest_session_id(manifest.campaign_id)
    finally:
        conn.close()

    session_number = _next_session_number(latest_session)
    typer.echo(
        f"Campaign: {manifest.campaign_name} \u00b7 Session: {session_number} \u00b7 Last turn: {last_turn}"
    )


def _next_session_number(last_session_id: object) -> int:
    if not isinstance(last_session_id, str):
        return 1
    prefix, sep, suffix = last_session_id.rpartition("_")
    if sep and prefix == "session" and suffix.isdigit():
        return int(suffix) + 1
    return 1
