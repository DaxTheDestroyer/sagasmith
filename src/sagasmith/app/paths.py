"""CampaignPaths value object and resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CampaignPaths:
    """Derived filesystem paths for a campaign directory."""

    root: Path  # <campaign_dir>
    manifest: Path  # root / "campaign.toml"
    db: Path  # root / "campaign.sqlite"
    player_vault: Path  # root / "player_vault"


def resolve_campaign_paths(root: Path) -> CampaignPaths:
    """Return CampaignPaths derived from *root* without touching the filesystem."""
    return CampaignPaths(
        root=root,
        manifest=root / "campaign.toml",
        db=root / "campaign.sqlite",
        player_vault=root / "player_vault",
    )


def validate_campaign_paths(paths: CampaignPaths) -> None:
    """Raise ValueError naming the first missing path component.

    Checked in order: manifest, db, player_vault.
    Plan 03-03 calls this to ensure a campaign is fully initialised before
    launching the TUI.
    """
    if not paths.manifest.is_file():
        raise ValueError(f"campaign directory missing: {paths.manifest}")
    if not paths.db.is_file():
        raise ValueError(f"campaign directory missing: {paths.db}")
    if not paths.player_vault.is_dir():
        raise ValueError(f"campaign directory missing: {paths.player_vault}")
