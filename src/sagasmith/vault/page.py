"""Vault page frontmatter models.

All page frontmatter inherit from BaseVaultFrontmatter. Each page type adds
its required fields and sets the `type` constant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from ..schemas.common import SchemaModel


class BaseVaultFrontmatter(SchemaModel):
    """Common frontmatter for all vault pages."""

    model_config = ConfigDict(extra="allow", strict=True, frozen=False)

    id: str = Field(..., description="Slug identifier, unique within its type.")
    type: str  # set by subclass as a const
    name: str
    aliases: list[str] = Field(default_factory=list)
    visibility: Literal["player_known", "foreshadowed", "gm_only"] = Field(
        default="gm_only", description="Visibility state for two-vault projection."
    )
    first_encountered: str | None = Field(
        default=None, description="Session ID of first appearance."
    )
    # GM-only fields; stripped from player vault projection
    gm_notes: str | None = None
    secrets: object | None = None


class NpcFrontmatter(BaseVaultFrontmatter):
    """Non-player character page."""

    type: str = "npc"
    species: str
    role: str
    status: str
    disposition_to_pc: str
    voice: str | None = None
    location_current: str | None = None
    factions: list[str] = Field(default_factory=list)


class LocationFrontmatter(BaseVaultFrontmatter):
    """Location / place page."""

    type: str = "location"
    settlement: str | None = None
    region: str | None = None
    connects_to: list[str] = Field(default_factory=list)
    terrain_tags: list[str] = Field(default_factory=list)
    status: str


class FactionFrontmatter(BaseVaultFrontmatter):
    """Faction / organization page."""

    type: str = "faction"
    alignment: str
    disposition_to_pc: str
    power_level: str
    known_members: list[str] = Field(default_factory=list)


class ItemFrontmatter(BaseVaultFrontmatter):
    """Item / object page."""

    type: str = "item"
    rarity: str
    held_by: str | None = None
    given_by: str | None = None
    given_in: str | None = None
    pf2e_ref: object | None = None


class QuestFrontmatter(BaseVaultFrontmatter):
    """Quest / plot thread page."""

    type: str = "quest"
    status: str  # active, completed_success, completed_failure, completed_abandoned
    given_by: str | None = None
    session_opened: str | None = None
    session_closed: str | None = None
    callbacks: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)


class CallbackFrontmatter(BaseVaultFrontmatter):
    """Callback seed page."""

    type: str = "callback"
    status: str  # open, paid_off, abandoned
    seeded_in: str | None = None
    paid_off_in: str | None = None
    seeded_by: str | None = None
    related_quest: str | None = None


class SessionFrontmatter(BaseVaultFrontmatter):
    """Session log page."""

    type: str = "session"
    number: int
    date_real: str  # ISO date
    date_in_game: str
    location_start: str | None = None
    location_end: str | None = None
    npcs_encountered: list[str] = Field(default_factory=list)
    quests_opened: list[str] = Field(default_factory=list)
    quests_closed: list[str] = Field(default_factory=list)
    callbacks_seeded: list[str] = Field(default_factory=list)
    callbacks_paid_off: list[str] = Field(default_factory=list)


class LoreFrontmatter(BaseVaultFrontmatter):
    """Lore / background information page."""

    type: str = "lore"
    category: str | None = None


# Union type for all supported NPC page types (per VAULT_SCHEMA §5)
NPC_PAGE_TYPES = (NpcFrontmatter,)

# All frontmatter types in membership order for discriminated union checks
_ALL_FRONTMATTER_TYPES = (
    NpcFrontmatter,
    LocationFrontmatter,
    FactionFrontmatter,
    ItemFrontmatter,
    QuestFrontmatter,
    CallbackFrontmatter,
    SessionFrontmatter,
    LoreFrontmatter,
)


class VaultPage:
    """A complete vault page: frontmatter + markdown body.

    Instances are immutable after construction. The writer serializes and
    atomically writes them to disk.
    """

    def __init__(self, frontmatter: BaseVaultFrontmatter, body: str = ""):
        self.frontmatter = frontmatter
        self.body = body or ""

    def as_markdown(self) -> str:
        """Serialize to full markdown with YAML frontmatter."""
        import yaml

        front_dict = self.frontmatter.model_dump(mode="json", exclude_none=True)
        yaml_str = yaml.safe_dump(front_dict, sort_keys=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n\n{self.body}"

    @classmethod
    def load_file(cls, path: Path) -> VaultPage:
        """Read and parse a vault file from disk."""
        import yaml

        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            _, front_yaml, body = text.split("---\n", 2)
            loaded: Any = yaml.safe_load(front_yaml) or {}
            front_dict: dict[str, Any] = (
                {str(key): value for key, value in loaded.items()}
                if isinstance(loaded, dict)
                else {}
            )
            frontmatter = cls._frontmatter_from_dict(front_dict)
        else:
            frontmatter = BaseVaultFrontmatter(id="orphan", type="lore", name="Orphan")
            body = text
        return cls(frontmatter, body)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VaultPage:
        """Reconstruct a VaultPage from a serializable dict (frontmatter + body)."""
        front_dict = data["frontmatter"]
        frontmatter = cls._frontmatter_from_dict(front_dict)
        body = data.get("body", "")
        return cls(frontmatter, body)

    @staticmethod
    def _frontmatter_from_dict(front_dict: dict[str, Any]) -> BaseVaultFrontmatter:
        """Instantiate the correct frontmatter subclass from a dict."""
        ftype = front_dict.get("type")
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
        cls_type = (
            mapping.get(ftype, BaseVaultFrontmatter)
            if isinstance(ftype, str)
            else BaseVaultFrontmatter
        )
        return cls_type.model_validate(front_dict)
