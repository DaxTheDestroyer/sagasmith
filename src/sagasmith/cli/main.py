"""SagaSmith command-line interface."""

from pathlib import Path
from typing import Annotated

import typer

import sagasmith
from sagasmith.cli.configure_cmd import configure_command
from sagasmith.cli.init_cmd import init_command
from sagasmith.cli.onboard_cmd import onboard_command
from sagasmith.cli.play_cmd import play_command
from sagasmith.cli.schema_cmd import schema_app
from sagasmith.cli.smoke_cmd import smoke
from sagasmith.cli.vault_cmd import vault_app

app = typer.Typer(help="SagaSmith — local-first AI-run solo TTRPG.", no_args_is_help=True)
app.add_typer(schema_app, name="schema")
app.add_typer(vault_app, name="vault")
app.command("smoke")(smoke)
app.command(name="init")(init_command)
app.command(name="onboard")(onboard_command)
app.command(name="play")(play_command)
app.command(name="configure")(configure_command)


@app.callback()
def main(ctx: typer.Context) -> None:
    """SagaSmith command group."""


@app.command()
def version() -> None:
    """Print the SagaSmith package version."""
    typer.echo(sagasmith.__version__)


@app.command()
def demo(
    campaign: Annotated[Path, typer.Option("--campaign", "-c")],
    mode: Annotated[str, typer.Option("--mode")] = "fast",
) -> None:
    """Run the no-paid-call smoke suite against a campaign. CLI-05."""
    from sagasmith.app.campaign_ref import open_campaign_ref
    from sagasmith.evals.harness import run_smoke

    try:
        opened = open_campaign_ref(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None
    manifest = opened.manifest

    typer.echo(f"Demo mode: campaign={manifest.campaign_name} provider=fake")
    result = run_smoke()
    typer.echo(result.format())
    if not result.ok:
        raise typer.Exit(code=1)
