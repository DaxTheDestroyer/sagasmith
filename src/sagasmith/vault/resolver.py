"""Entity resolution by slug and alias."""

from __future__ import annotations

import re
from pathlib import Path

from .page import VaultPage

# Mapping from entity_type (as used in frontmatter 'type') to filename prefix
_TYPE_PREFIX: dict[str, str] = {
    "npc": "npc_",
    "pc": "pc_",
    "location": "loc_",
    "faction": "fac_",
    "item": "item_",
    "quest": "quest_",
    "callback": "cb_",
    "session": "session_",
    "lore": "lore_",
}


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug for vault filenames.

    Rules:
    - Lowercase
    - Replace spaces and hyphens with underscores
    - Remove non-alphanumeric characters except underscore
    - Strip leading/trailing whitespace and underscores
    """
    slug = name.lower().strip()
    slug = re.sub(r"[\s\-]+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug


class EntityResolver:
    """Resolves entity names to canonical VaultPage records.

    Scans the master vault directory on initialization and builds two
    indexes: slug → page and alias → page. The resolve() method performs
    slug matching (prefixed with type code when entity_type is known) followed
    by case-insensitive alias lookup.
    """

    def __init__(self, master_vault_path: Path):
        self.master_vault_path = Path(master_vault_path)
        self._slug_index: dict[str, VaultPage] = {}
        self._alias_index: dict[str, VaultPage] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        """Scan all markdown files in master vault and populate indexes."""
        if not self.master_vault_path.exists():
            return
        for md_file in self.master_vault_path.rglob("*.md"):
            try:
                page = VaultPage.load_file(md_file)
            except Exception:
                # Skip unparsable files; they'll be handled by repair CLI later
                continue
            fm = page.frontmatter
            # Index by slug (id)
            self._slug_index[fm.id] = page
            # Index aliases (case-folded)
            for alias in fm.aliases:
                self._alias_index[alias.lower()] = page

    def resolve(self, name: str, entity_type: str | None = None) -> VaultPage | None:
        """Find a vault page by name using slug or alias.

        Resolution order:
        1. If entity_type is known, compute prefixed slug and look in slug index.
        2. Otherwise, try alias match (always works).
        3. If entity_type given, also filter by type.

        Args:
            name: The raw entity name to look up.
            entity_type: Optional type filter ("npc", "location", etc.).

        Returns:
            The matching VaultPage or None if no match found.
        """
        # Try slug match first if we know the entity type.
        if entity_type is not None:
            prefix = _TYPE_PREFIX.get(entity_type)
            if prefix:
                candidate_id = f"{prefix}{slugify(name)}"
                page = self._slug_index.get(candidate_id)
                if page is not None:
                    return page
        else:
            # Unknown type: try every supported filename prefix before aliases.
            # This prevents duplicate pages when the canonical name matches but
            # the page has no aliases yet.
            slug = slugify(name)
            for prefix in _TYPE_PREFIX.values():
                page = self._slug_index.get(f"{prefix}{slug}")
                if page is not None:
                    return page
        # Try alias match (case-insensitive)
        page = self._alias_index.get(name.lower())
        if page is not None and (
            entity_type is None or getattr(page.frontmatter, "type", None) == entity_type
        ):
            return page
        return None

    def refresh(self) -> None:
        """Re-scan the vault to pick up new pages (used after writes)."""
        self._slug_index.clear()
        self._alias_index.clear()
        self._build_indexes()
