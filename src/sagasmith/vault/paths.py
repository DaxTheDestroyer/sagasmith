"""Vault path resolution helpers."""

from __future__ import annotations

import os
from pathlib import Path


def _default_master_vault() -> Path:
    """Default master vault location (~/.ttrpg/vault)."""
    home = Path.home()
    base = Path(os.environ.get("APPDATA", home)) if os.name == "nt" else home
    return base / ".ttrpg" / "vault"


DEFAULT_MASTER_OPTS = _default_master_vault()


def get_master_vault_path(campaign_id: str) -> Path:
    """Return the master vault directory for a campaign."""
    # campaign_id should be slug-safe; we trust bootstrap
    return DEFAULT_MASTER_OPTS / campaign_id


def ensure_player_vault_path(campaign_root: Path) -> Path:
    """Return the player vault directory within the campaign folder, creating it."""
    player_vault = campaign_root / "player_vault"
    player_vault.mkdir(parents=True, exist_ok=True)
    return player_vault
