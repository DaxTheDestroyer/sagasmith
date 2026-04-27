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
    from sagasmith.app.campaign import open_campaign
    from sagasmith.persistence.db import open_campaign_db

    try:
        paths, manifest = open_campaign(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    conn = open_campaign_db(paths.db, read_only=True)
    try:
        row = conn.execute(
            "SELECT turn_id FROM turn_records WHERE status='complete' ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    last_turn = row[0] if row else "none"
    # TODO(Phase 7): session_id will come from a sessions table; MVP keeps session_id=1.
    typer.echo(f"Campaign: {manifest.campaign_name} \u00b7 Session: 1 \u00b7 Last turn: {last_turn}")
