"""Campaign-level Pydantic schemas: CampaignManifest and ProviderSettings."""

from __future__ import annotations

import re
import secrets
from typing import Literal

from sagasmith.schemas.common import SchemaModel
from sagasmith.services.secrets import SecretRef


class CampaignManifest(SchemaModel):
    """On-disk manifest written to campaign.toml on init."""

    manifest_version: Literal[1]
    campaign_id: str
    campaign_name: str
    campaign_slug: str
    created_at: str  # ISO 8601 UTC
    sagasmith_version: str
    schema_version: int

    @classmethod
    def _validate_slug(cls, slug: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", slug):
            raise ValueError(
                "campaign_slug must be lowercase alphanumeric with hyphens, "
                "≤ 40 chars, not leading hyphen"
            )
        return slug

    def model_post_init(self, __context: object) -> None:
        self._validate_slug(self.campaign_slug)


class ProviderSettings(SchemaModel):
    """Provider configuration stored in the settings SQLite table."""

    provider: Literal["openrouter", "fake"]
    api_key_ref: SecretRef | None  # None for `fake`
    default_model: str
    narration_model: str
    cheap_model: str
    pricing_mode: Literal["provider_reported", "static_table"] = "static_table"


def generate_campaign_id(slug: str) -> str:
    """Return a collision-resistant campaign ID: ``<slug>-<8 hex chars>``."""
    # Use secrets (not random) for non-guessable but non-security-sensitive IDs.
    return f"{slug}-{secrets.token_hex(4)}"
