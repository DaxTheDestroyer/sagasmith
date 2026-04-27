"""CLI command: ``sagasmith play`` — resume an existing campaign. CLI-03."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sagasmith.app.campaign import open_campaign
from sagasmith.persistence.db import open_campaign_db


def play_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c", help="Campaign directory path.")],
) -> None:
    """Resume a campaign. CLI-03.

    NOTE: Plan 03-03 replaces the stub body with a Textual app launch. This
    plan implements the resume-status line and exit-code contract only.
    """
    try:
        paths, manifest = open_campaign(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    conn = open_campaign_db(paths.db, read_only=True)
    try:
        # Count completed turns.
        row = conn.execute(
            "SELECT COUNT(*) FROM turn_records WHERE status = 'complete'"
        ).fetchone()
        _turn_count = row[0] if row else 0

        # Get last completed turn ID.
        row2 = conn.execute(
            "SELECT turn_id FROM turn_records WHERE status='complete' ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
        last_turn_id = row2[0] if row2 else "none"
    finally:
        conn.close()

    # TODO(Phase 7): session_id will come from a sessions table; MVP keeps session_id=1.
    typer.echo(
        f"Campaign: {manifest.campaign_name} · Session: 1 · Last turn: {last_turn_id}"
    )
