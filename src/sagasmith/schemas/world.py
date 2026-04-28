"""World bible schema for hidden Oracle campaign context."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import SchemaModel


class WorldLocation(SchemaModel):
    """A significant location in the hidden campaign world bible."""

    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list[str])
    secrets: list[str] = Field(default_factory=list[str])


class WorldFaction(SchemaModel):
    """A faction or power group with agenda-bearing context."""

    id: str
    name: str
    public_face: str
    agenda: str
    relationships: list[str] = Field(default_factory=list[str])


class WorldNpc(SchemaModel):
    """Important non-player character context owned by the Oracle."""

    id: str
    name: str
    role: str
    motivation: str
    faction_id: str | None = None
    secret: str | None = None


class WorldConflict(SchemaModel):
    """A core campaign tension the Oracle can turn into scenes."""

    id: str
    name: str
    summary: str
    stakes: str
    involved_factions: list[str] = Field(default_factory=list[str])


class MagicRulesContext(SchemaModel):
    """Setting-facing magic/system assumptions for narration and planning."""

    magic_prevalence: str
    divine_presence: str
    technology_level: str
    pf2e_assumptions: list[str] = Field(default_factory=list[str])


class WorldBible(SchemaModel):
    """Hidden, validated setting bible generated once from onboarding records."""

    theme: str
    tone: list[str] = Field(min_length=1)
    genre_elements: list[str] = Field(min_length=1)
    core_themes: list[str] = Field(min_length=1)
    key_locations: list[WorldLocation] = Field(min_length=2)
    factions: list[WorldFaction] = Field(min_length=1)
    important_npcs: list[WorldNpc] = Field(min_length=1)
    core_conflicts: list[WorldConflict] = Field(min_length=1)
    magic_rules: MagicRulesContext
    safety_notes: list[str] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def _ids_are_unique(self) -> WorldBible:
        groups: list[tuple[str, list[str]]] = [
            ("key_locations", [item.id for item in self.key_locations]),
            ("factions", [item.id for item in self.factions]),
            ("important_npcs", [item.id for item in self.important_npcs]),
            ("core_conflicts", [item.id for item in self.core_conflicts]),
        ]
        for field_name, ids in groups:
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field_name} ids must be unique")
        return self
