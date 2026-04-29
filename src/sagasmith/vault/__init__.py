"""Vault service: deterministic storage layer for campaign canon.

Provides path resolution, atomic page writes with post-write validation,
entity resolution by slug/alias, player-vault projection sync, and the
top-level service object injected into agent services.
"""

from __future__ import annotations

import re
from pathlib import Path

from .page import (
    NPC_PAGE_TYPES,
    BaseVaultFrontmatter,
    CallbackFrontmatter,
    FactionFrontmatter,
    ItemFrontmatter,
    LocationFrontmatter,
    LoreFrontmatter,
    NpcFrontmatter,
    QuestFrontmatter,
    SessionFrontmatter,
    VaultPage,
)
from .paths import ensure_player_vault_path, get_master_vault_path
from .resolver import EntityResolver
from .writer import atomic_write

__all__ = [
    "NPC_PAGE_TYPES",
    "BaseVaultFrontmatter",
    "EntityResolver",
    "VaultPage",
    "VaultService",
    "atomic_write",
    "ensure_player_vault_path",
    "get_master_vault_path",
]


class VaultService:
    """Owns vault roots and entity resolution.

    The Archivist uses this service to write pages, resolve entities, and
    sync the player vault projection.
    """

    def __init__(self, campaign_id: str, player_vault_root: Path):
        self.master_path = get_master_vault_path(campaign_id)
        self.player_vault_root = player_vault_root
        self._resolver = EntityResolver(self.master_path)

    @property
    def resolver(self) -> EntityResolver:
        """Entity resolution engine for the master vault."""
        return self._resolver

    def write_page(self, page: VaultPage, relative_path: Path, *, is_master: bool = True) -> Path:
        """Atomically write a vault page to the appropriate vault.

        Args:
            page: The vault page to write.
            relative_path: Path relative to vault root (e.g. 'npc/orym_the_humble.md').
            is_master: If True, write to master vault; else to player vault.

        Returns:
            The absolute path of the written file.
        """
        base = self.master_path if is_master else self.player_vault_root
        target = base / relative_path
        atomic_write(page, target)
        return target

    def ensure_master_path(self) -> None:
        """Ensure master vault directory exists."""
        self.master_path.mkdir(parents=True, exist_ok=True)

    def ensure_player_vault(self) -> None:
        """Ensure player vault directory exists."""
        self.player_vault_root.mkdir(parents=True, exist_ok=True)

    def sync(self) -> None:
        """Project master vault to player vault with visibility filtering.

        For each page in master vault:
        - gm_only: skip (not written to player vault)
        - foreshadowed: write stub with minimal frontmatter, empty body
        - player_known: write full page with GM-only fields stripped from
          frontmatter and body (comments between <!-- gm: ... --> removed).

        Atomic writes per file; failures raise ValueError.
        """
        self.ensure_player_vault()
        # Walk master vault; skip meta/ (master-only)
        for md_file in self.master_path.rglob("*.md"):
            rel = md_file.relative_to(self.master_path)
            if rel.parts and rel.parts[0] == "meta":
                # meta pages are master-only; never projected
                continue
            page = VaultPage.load_file(md_file)
            visibility = page.frontmatter.visibility
            if visibility == "gm_only":
                continue
            if visibility == "foreshadowed":
                # Create stub: only id, type, name, aliases
                stub_front = BaseVaultFrontmatter(
                    id=page.frontmatter.id,
                    type=page.frontmatter.type,
                    name=page.frontmatter.name,
                    aliases=page.frontmatter.aliases or [],
                    visibility="foreshadowed",
                    first_encountered=page.frontmatter.first_encountered,
                )
                stub_page = VaultPage(stub_front, body="")
                target = self.player_vault_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(stub_page, target)
            elif visibility == "player_known":
                # Strip gm fields and inline comments; write full content
                front_dict = page.frontmatter.model_dump(mode="json")
                # Remove GM-only keys
                gm_keys = {"secrets", "gm_notes"} | {k for k in front_dict if k.startswith("gm_")}
                for k in gm_keys:
                    front_dict.pop(k, None)
                target_cls = _frontmatter_type_for(front_dict.get("type"))
                clean_front = target_cls.model_validate(front_dict)
                # Strip body GM comments
                clean_body = _strip_gm_comments(page.body)
                clean_page = VaultPage(clean_front, clean_body)
                target = self.player_vault_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(clean_page, target)
            else:
                # Unknown visibility: skip to be safe
                continue
                # Regenerate index.md and log.md (simplified stub: not implemented in first slice)
                # Plan 07-05 will flesh out index and log.


def _strip_gm_comments(body: str) -> str:
    """Remove all <!-- gm: ... --> comment blocks from body text."""
    # Regex matches <!-- gm: ... --> possibly spanning newlines (non-greedy)
    pattern = re.compile(r"<!--\s*gm:.*?-->", re.DOTALL)
    return pattern.sub("", body)


def _frontmatter_type_for(type_name: object) -> type[BaseVaultFrontmatter]:
    mapping: dict[str, type[BaseVaultFrontmatter]] = {
        "npc": NpcFrontmatter,
        "location": LocationFrontmatter,
        "faction": FactionFrontmatter,
        "item": ItemFrontmatter,
        "quest": QuestFrontmatter,
        "callback": CallbackFrontmatter,
        "session": SessionFrontmatter,
        "lore": LoreFrontmatter,
    }
    return mapping.get(type_name, BaseVaultFrontmatter) if isinstance(type_name, str) else BaseVaultFrontmatter
