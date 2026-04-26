"""SagaSmith command-line interface."""

import typer

import sagasmith
from sagasmith.cli.schema_cmd import schema_app
from sagasmith.cli.smoke_cmd import smoke

app = typer.Typer(help="SagaSmith — local-first AI-run solo TTRPG.", no_args_is_help=True)
app.add_typer(schema_app, name="schema")
app.command("smoke")(smoke)


@app.callback()
def main(ctx: typer.Context) -> None:
    """SagaSmith command group."""


@app.command()
def version() -> None:
    """Print the SagaSmith package version."""
    typer.echo(sagasmith.__version__)
