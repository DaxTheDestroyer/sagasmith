"""CLI command: ``sagasmith configure`` — update provider/model settings. CLI-04."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pydantic
import typer

from sagasmith.app.campaign import open_campaign
from sagasmith.app.config import SettingsRepository
from sagasmith.persistence.db import open_campaign_db
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.services.secrets import SecretRef


def _parse_api_key_ref(raw: str | None) -> SecretRef | None:
    """Parse ``--api-key-ref`` argument into a :class:`SecretRef`.

    Accepted formats:
    - ``env:VAR``                  → ``SecretRef(kind="env", name="VAR")``
    - ``keyring:service:account``  → ``SecretRef(kind="keyring", name="service", account="account")``

    Returns ``None`` if *raw* is ``None`` (leave current value unchanged).
    Exits 2 if the format is not recognised.
    """
    if raw is None:
        return None
    if raw.startswith("env:"):
        parts = raw.split(":", 1)
        if len(parts) == 2 and parts[1]:
            return SecretRef(kind="env", name=parts[1])
    elif raw.startswith("keyring:"):
        parts = raw.split(":", 2)
        if len(parts) == 3 and parts[1] and parts[2]:
            return SecretRef(kind="keyring", name=parts[1], account=parts[2])
    typer.echo("api_key_ref must be 'env:VAR' or 'keyring:service:account'", err=True)
    raise typer.Exit(code=2)


def configure_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c")],
    provider: Annotated[str | None, typer.Option("--provider", help="openrouter | fake")] = None,
    api_key_ref: Annotated[
        str | None,
        typer.Option("--api-key-ref", help="'env:VAR' or 'keyring:service:account'"),
    ] = None,
    default_model: Annotated[str | None, typer.Option("--default-model")] = None,
    narration_model: Annotated[str | None, typer.Option("--narration-model")] = None,
    cheap_model: Annotated[str | None, typer.Option("--cheap-model")] = None,
) -> None:
    """Update provider/model settings for an existing campaign. Merges with current values."""
    try:
        _paths, manifest = open_campaign(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    parsed_ref = _parse_api_key_ref(api_key_ref)

    conn = open_campaign_db(_paths.db)
    try:
        repo = SettingsRepository(conn)
        current = repo.get_provider_settings(manifest.campaign_id)
        if current is None:
            typer.echo("campaign has no provider settings; re-run init", err=True)
            raise typer.Exit(code=2)

        # Merge CLI overrides into existing settings; track which keys change.
        changed: list[str] = []
        new_provider = current.provider if provider is None else provider  # type: ignore[assignment]
        if new_provider != current.provider:
            changed.append("provider")

        new_api_key_ref = current.api_key_ref if parsed_ref is None else parsed_ref
        if new_api_key_ref != current.api_key_ref:
            changed.append("api_key_ref")

        new_default_model = current.default_model if default_model is None else default_model
        if new_default_model != current.default_model:
            changed.append("default_model")

        new_narration_model = current.narration_model if narration_model is None else narration_model
        if new_narration_model != current.narration_model:
            changed.append("narration_model")

        new_cheap_model = current.cheap_model if cheap_model is None else cheap_model
        if new_cheap_model != current.cheap_model:
            changed.append("cheap_model")

        try:
            updated = ProviderSettings(
                provider=new_provider,  # type: ignore[arg-type]
                api_key_ref=new_api_key_ref,
                default_model=new_default_model,
                narration_model=new_narration_model,
                cheap_model=new_cheap_model,
                pricing_mode=current.pricing_mode,
            )
        except (pydantic.ValidationError, ValueError) as exc:
            typer.echo(f"error: invalid settings value: {exc}", err=True)
            raise typer.Exit(code=2) from None
        with conn:
            repo.put_provider_settings(manifest.campaign_id, updated)
    finally:
        conn.close()

    # NEVER print the resolved secret — only print the changed key names.
    typer.echo(f"Updated provider settings for campaign '{manifest.campaign_name}'")
    if changed:
        typer.echo(f"  changed keys: {', '.join(changed)}")
