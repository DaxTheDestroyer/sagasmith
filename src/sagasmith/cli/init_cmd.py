"""CLI command: ``sagasmith init`` — initialise a new local campaign. CLI-01, CLI-02."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import pydantic
import typer

from sagasmith.app.campaign import init_campaign, slugify
from sagasmith.services.secrets import SecretRef


def init_command(
    name: Annotated[str | None, typer.Option("--name", "-n", help="Campaign display name.")] = None,
    path: Annotated[
        Path | None, typer.Option("--path", "-p", help="Campaign directory (default: ./<slug>).")
    ] = None,
    provider: Annotated[str, typer.Option("--provider", help="openrouter | fake")] = "fake",
    api_key_env: Annotated[
        str | None,
        typer.Option("--api-key-env", help="Env var name holding the API key (for openrouter)."),
    ] = None,
) -> None:
    """Initialize a new local campaign. CLI-01, CLI-02."""
    # Resolve name — prompt if TTY, fail loudly in non-interactive mode.
    resolved_name: str
    if name is None:
        if sys.stdin.isatty():
            resolved_name = typer.prompt("Campaign name")
        else:
            typer.echo("--name is required in non-interactive mode", err=True)
            raise typer.Exit(code=2)
    else:
        resolved_name = name

    slug = slugify(resolved_name)

    # Resolve path — prompt if TTY (with default), else use deterministic default.
    resolved_path: Path
    if path is None:
        default_path = Path.cwd() / slug
        if sys.stdin.isatty():
            raw = typer.prompt("Campaign directory", default=str(default_path))
            resolved_path = Path(raw)
        else:
            resolved_path = default_path
    else:
        resolved_path = path

    # Validate openrouter requires api_key_env in non-interactive mode.
    if provider == "openrouter" and api_key_env is None:
        if sys.stdin.isatty():
            api_key_env = typer.prompt("Env var name holding the OpenRouter API key")
        else:
            typer.echo(
                "--api-key-env is required for provider=openrouter in non-interactive mode",
                err=True,
            )
            raise typer.Exit(code=2)

    api_key_ref = SecretRef(kind="env", name=api_key_env) if api_key_env else None

    try:
        manifest = init_campaign(
            name=resolved_name,
            root=resolved_path,
            provider=provider,  # type: ignore[arg-type]
            api_key_ref=api_key_ref,
        )
    except FileExistsError:
        typer.echo(f"Campaign already exists at {resolved_path}", err=True)
        raise typer.Exit(code=1) from None
    except (pydantic.ValidationError, ValueError) as exc:
        typer.echo(f"error: invalid provider value: {exc}", err=True)
        raise typer.Exit(code=2) from None

    typer.echo(f"Initialized campaign '{resolved_name}' at {resolved_path}")
    typer.echo(f"  campaign_id: {manifest.campaign_id}")
    typer.echo(f"  schema_version: {manifest.schema_version}")
