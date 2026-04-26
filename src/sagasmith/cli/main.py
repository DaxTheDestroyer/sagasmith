"""SagaSmith command-line interface."""

import typer

import sagasmith

app = typer.Typer(help="SagaSmith — local-first AI-run solo TTRPG.", no_args_is_help=True)


@app.callback()
def main(ctx: typer.Context) -> None:
    """SagaSmith command group."""


@app.command()
def version() -> None:
    """Print the SagaSmith package version."""
    typer.echo(sagasmith.__version__)
