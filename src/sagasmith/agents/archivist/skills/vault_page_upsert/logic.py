"""Logic for vault-page-upsert skill."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import (
    BaseVaultFrontmatter,
    CallbackFrontmatter,
    FactionFrontmatter,
    ItemFrontmatter,
    LocationFrontmatter,
    LoreFrontmatter,
    NpcFrontmatter,
    QuestFrontmatter,
    SessionFrontmatter,
)
from sagasmith.vault.resolver import slugify

# Mapping from type string to frontmatter class, prefix, and subfolder
_TYPE_MAP: dict[str, tuple[type[BaseVaultFrontmatter], str, str]] = {
    "npc": (NpcFrontmatter, "npc_", "npcs"),
    "pc": (NpcFrontmatter, "pc_", "pcs"),
    "location": (LocationFrontmatter, "loc_", "locations"),
    "faction": (FactionFrontmatter, "fac_", "factions"),
    "item": (ItemFrontmatter, "item_", "items"),
    "quest": (QuestFrontmatter, "quest_", "quests"),
    "callback": (CallbackFrontmatter, "cb_", "callbacks"),
    "session": (SessionFrontmatter, "session_", "sessions"),
    "lore": (LoreFrontmatter, "lore_", "lore"),
}


@dataclass(frozen=True)
class VaultPageUpsertResult:
    """Validated vault page prepared for turn-close persistence."""

    page: VaultPage
    relative_path: Path
    action: str


def _find_unique_slug(base_slug: str, target_dir: Path, prefix: str) -> str:
    """Find a unique page ID by appending _2, _3, ... if needed."""
    candidate = target_dir / f"{prefix}{base_slug}.md"
    if not candidate.exists():
        return f"{prefix}{base_slug}"
    counter = 2
    while True:
        candidate = target_dir / f"{prefix}{base_slug}_{counter}.md"
        if not candidate.exists():
            return f"{prefix}{base_slug}_{counter}"
        counter += 1


def vault_page_upsert(
    *,
    vault_service: VaultService,
    entity_draft: dict[str, object],
    visibility: str,
    session_number: int | str,
) -> VaultPageUpsertResult:
    """Prepare a validated vault page without touching the filesystem.

    Args:
        vault_service: VaultService instance with master vault path.
        entity_draft: Dictionary containing entity fields (must have 'name' and 'type').
        visibility: Visibility state — "player_known", "foreshadowed", or "gm_only".
        session_number: Session number to record in first_encountered.

    Returns:
        VaultPageUpsertResult containing the page, relative path, and action.

    Raises:
        ValueError: If required fields missing or frontmatter validation fails.
    """
    # Validate required inputs
    raw_name = entity_draft.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError("entity_draft must contain a non-empty 'name'")
    name = raw_name.strip()
    entity_type = entity_draft.get("type")
    if not isinstance(entity_type, str):
        raise ValueError("entity_draft must contain a string 'type'")

    type_info = _TYPE_MAP.get(entity_type)
    if type_info is None:
        raise ValueError(f"Unsupported entity type: {entity_type!r}")

    frontmatter_cls, prefix, subfolder = type_info

    # Compute slug and ensure master vault exists
    slug = slugify(name)
    vault_service.ensure_master_path()
    target_dir = vault_service.master_path / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine if this is an update (explicit id matching an existing file)
    existing_id = entity_draft.get("id")
    existing_page = None
    target_path_candidate: Path | None = None

    if isinstance(existing_id, str) and existing_id.strip():
        # Explicit id: check file exists directly under subfolder
        candidate = vault_service.master_path / subfolder / f"{existing_id}.md"
        if candidate.exists():
            existing_page = VaultPage.load_file(candidate)
            target_path_candidate = candidate

    if existing_page is not None:
        # Update existing page at its known location
        assert target_path_candidate is not None
        target_path = target_path_candidate
        action = "updated"
        # Merge draft into existing frontmatter fields
        frontmatter_dict = existing_page.frontmatter.model_dump()
        draft_clean = {k: v for k, v in entity_draft.items() if k not in ("id", "type")}
        frontmatter_dict.update(draft_clean)
        frontmatter_dict["visibility"] = visibility
        # Preserve original first_encountered
        frontmatter = frontmatter_cls.model_validate(frontmatter_dict)
        page = VaultPage(frontmatter, body=existing_page.body)
    else:
        # Create new page — resolve slug collision
        page_id = _find_unique_slug(slug, target_dir, prefix)
        target_path = target_dir / f"{page_id}.md"

        # Build frontmatter dict from draft with defaults
        frontmatter_dict: dict[str, object] = {
            "id": page_id,
            "type": entity_type,
            "name": name,
            "visibility": visibility,
            "first_encountered": str(session_number),
        }
        # Copy remaining draft fields
        for key, value in entity_draft.items():
            if key not in ("id", "type") and key not in frontmatter_dict:
                frontmatter_dict[key] = value

        frontmatter = _prepare_frontmatter(frontmatter_cls, frontmatter_dict)
        action = "created"
        page = VaultPage(frontmatter, body="")

    return VaultPageUpsertResult(
        page=page,
        relative_path=target_path.relative_to(vault_service.master_path),
        action=action,
    )


def _prepare_frontmatter(
    cls: type[BaseVaultFrontmatter], data: dict[str, object]
) -> BaseVaultFrontmatter:
    """Validate and return a frontmatter instance, filling minimal defaults."""
    # Fill common Base fields
    if "aliases" not in data:
        data["aliases"] = []
    if "gm_notes" not in data:
        data["gm_notes"] = None
    if "secrets" not in data:
        data["secrets"] = None

    # Type-specific defaults
    if cls is NpcFrontmatter:
        data.setdefault("species", "humanoid")
        data.setdefault("role", "unknown")
        data.setdefault("status", "alive")
        data.setdefault("disposition_to_pc", "neutral")
    elif cls is LocationFrontmatter:
        data.setdefault("settlement", None)
        data.setdefault("region", None)
        data.setdefault("connects_to", [])
        data.setdefault("terrain_tags", [])
        data.setdefault("status", "unknown")
    elif cls is FactionFrontmatter:
        data.setdefault("alignment", "neutral")
        data.setdefault("disposition_to_pc", "neutral")
        data.setdefault("power_level", "minor")
        data.setdefault("known_members", [])
    elif cls is ItemFrontmatter:
        data.setdefault("rarity", "common")
        data.setdefault("held_by", None)
        data.setdefault("given_by", None)
        data.setdefault("given_in", None)
        data.setdefault("pf2e_ref", None)
    elif cls is QuestFrontmatter:
        data.setdefault("status", "active")
        data.setdefault("given_by", None)
        data.setdefault("session_opened", None)
        data.setdefault("session_closed", None)
        data.setdefault("callbacks", [])
        data.setdefault("related_entities", [])
    elif cls is CallbackFrontmatter:
        data.setdefault("status", "open")
        data.setdefault("seeded_in", None)
        data.setdefault("paid_off_in", None)
        data.setdefault("seeded_by", None)
        data.setdefault("related_quest", None)
    elif cls is SessionFrontmatter:
        # Session-specific fields are typically filled by caller
        data.setdefault("number", 1)
        data.setdefault("date_real", "1970-01-01T00:00:00Z")
        data.setdefault("date_in_game", "unknown")
        data.setdefault("location_start", None)
        data.setdefault("location_end", None)
        data.setdefault("npcs_encountered", [])
        data.setdefault("quests_opened", [])
        data.setdefault("quests_closed", [])
        data.setdefault("callbacks_seeded", [])
        data.setdefault("callbacks_paid_off", [])
    elif cls is LoreFrontmatter:
        data.setdefault("category", None)

    try:
        return cls.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Frontmatter validation failed: {exc}") from exc
