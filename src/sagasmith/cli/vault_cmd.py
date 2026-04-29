"""Vault maintenance CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sagasmith.app.campaign import open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.vault import VaultService, VaultSyncError

vault_app = typer.Typer(help="Vault maintenance and repair commands")


@vault_app.command("rebuild")
def rebuild_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c", help="Campaign directory path.")],
) -> None:
    """Rebuild derived vault indices from the master vault."""
    try:
        paths, manifest = open_campaign(campaign)
        conn = open_campaign_db(paths.db, read_only=False)
        try:
            service = VaultService(
                campaign_id=manifest.campaign_id,
                player_vault_root=paths.player_vault,
            )
            service.rebuild_indices(conn)
        finally:
            conn.close()
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Vault indices rebuilt successfully.")


@vault_app.command("sync")
def sync_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c", help="Campaign directory path.")],
) -> None:
    """Force a spoiler-safe player-vault projection from the master vault."""
    try:
        paths, manifest = open_campaign(campaign)
        service = VaultService(
            campaign_id=manifest.campaign_id,
            player_vault_root=paths.player_vault,
        )
        service.sync()
    except VaultSyncError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Player vault synced.")
