"""Canonical entity-type registry shared by vault skills, persistence, and memory."""

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

# (frontmatter_cls, id_prefix, subfolder)
TYPE_MAP: dict[str, tuple[type[BaseVaultFrontmatter], str, str]] = {
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


def subfolder_for(page_type: str) -> str:
    """Return the vault subfolder for an entity type, falling back to 'lore'."""
    info = TYPE_MAP.get(page_type)
    return info[2] if info is not None else "lore"
