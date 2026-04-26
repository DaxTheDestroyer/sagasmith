"""Schema management CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sagasmith.schemas.export import export_all_schemas

schema_app = typer.Typer(help="Schema management commands.", no_args_is_help=True)


@schema_app.command("export")
def export_cmd(
    out: Annotated[
        Path,
        typer.Option("--out", help="Output directory for .schema.json files."),
    ] = Path("schemas"),
) -> None:
    """Export JSON Schema for every LLM-boundary or persisted model."""

    paths = export_all_schemas(out)
    for path in paths:
        typer.echo(str(path))
    typer.echo(f"Wrote {len(paths)} schema files to {out}")
