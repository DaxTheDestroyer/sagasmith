"""Campaign lifecycle: init_campaign, open_campaign, and slugify."""

from __future__ import annotations

import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import sagasmith
from sagasmith.app.config import SettingsRepository
from sagasmith.app.paths import CampaignPaths, resolve_campaign_paths, validate_campaign_paths
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.migrations import apply_migrations, current_schema_version
from sagasmith.schemas.campaign import (
    CampaignManifest,
    ProviderSettings,
    generate_campaign_id,
)
from sagasmith.services.secrets import SecretRef

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lowercase, replace non-[a-z0-9]+ with '-', strip leading/trailing '-', truncate to 40 chars.

    Guarantees the result passes the CampaignManifest slug validator.
    """
    lowered = name.lower()
    dashed = _SLUG_PATTERN.sub("-", lowered)
    stripped = dashed.strip("-")
    # Ensure we never produce an empty string
    if not stripped:
        stripped = "campaign"
    return stripped[:40]


def _write_toml(manifest: CampaignManifest, path: Path) -> None:
    """Minimal hand-rolled TOML writer for CampaignManifest scalar fields.

    We avoid adding the ``tomli_w`` dependency for six scalar fields.
    Supports str, int, bool top-level keys; TOML spec requires strings be
    double-quoted and integers/booleans unquoted.
    """
    lines: list[str] = []
    for field_name, value in manifest.model_dump().items():
        if isinstance(value, bool):
            lines.append(f"{field_name} = {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{field_name} = {value}")
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{field_name} = "{escaped}"')
        else:
            # Fallback: repr as string
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{field_name} = "{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def init_campaign(
    *,
    name: str,
    root: Path,
    provider: Literal["openrouter", "fake"] = "fake",
    api_key_ref: SecretRef | None = None,
    default_model: str = "fake/fake-default",
    narration_model: str = "fake/fake-narration",
    cheap_model: str = "fake/fake-cheap",
) -> CampaignManifest:
    """Create *root/*, write campaign.toml, run migrations, seed campaigns + settings rows.

    Idempotency: if the campaign directory already exists, raises
    :exc:`FileExistsError` — the caller (CLI) decides whether to prompt.
    Never overwrites silently.
    """
    # 1. Create root directory — raises FileExistsError if already exists.
    root.mkdir(parents=True, exist_ok=False)

    # 2. Create player_vault directory.
    (root / "player_vault").mkdir()

    # 3. Open DB, run migrations, record schema version.
    conn = open_campaign_db(root / "campaign.sqlite")
    try:
        apply_migrations(conn)
        schema_version_value = current_schema_version(conn)

        slug = slugify(name)
        campaign_id = generate_campaign_id(slug)
        created_at = datetime.now(UTC).isoformat()

        # 4. Seed campaigns + settings rows inside ONE transaction.
        with conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    campaign_id, campaign_name, campaign_slug,
                    created_at, sagasmith_version, manifest_version
                ) VALUES (?, ?, ?, ?, ?, 1)
                """,
                (campaign_id, name, slug, created_at, sagasmith.__version__),
            )
            provider_settings = ProviderSettings(
                provider=provider,
                api_key_ref=api_key_ref,
                default_model=default_model,
                narration_model=narration_model,
                cheap_model=cheap_model,
            )
            # 5. Write ProviderSettings through SettingsRepository (runs RedactionCanary).
            SettingsRepository(conn).put_provider_settings(campaign_id, provider_settings)
    finally:
        conn.close()

    # 6. Serialize CampaignManifest to TOML.
    manifest = CampaignManifest(
        manifest_version=1,
        campaign_id=campaign_id,
        campaign_name=name,
        campaign_slug=slug,
        created_at=created_at,
        sagasmith_version=sagasmith.__version__,
        schema_version=schema_version_value,
    )
    _write_toml(manifest, root / "campaign.toml")

    # 7. Return the manifest.
    return manifest


def open_campaign(root: Path) -> tuple[CampaignPaths, CampaignManifest]:
    """Validate layout and return paths + parsed manifest.

    Raises :exc:`ValueError` naming which file is missing so the CLI can show
    a specific error.
    """
    paths = resolve_campaign_paths(root)
    # validate_campaign_paths raises ValueError on any missing component.
    validate_campaign_paths(paths)

    raw = tomllib.loads(paths.manifest.read_text(encoding="utf-8"))
    manifest = CampaignManifest.model_validate(raw)
    return paths, manifest
