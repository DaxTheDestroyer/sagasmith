"""Campaign seed schema for Oracle opening hooks and first arc."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import SchemaModel


class PlotHook(SchemaModel):
    """A player-selectable opening hook aligned with onboarding preferences."""

    id: str
    title: str
    premise: str
    aligned_preferences: list[str] = Field(default_factory=list[str])
    initial_location_id: str | None = None
    featured_npc_ids: list[str] = Field(default_factory=list[str])
    conflict_id: str | None = None


class SeedArc(SchemaModel):
    """Initial campaign arc selected by the Oracle from the hook set."""

    title: str
    selected_hook_id: str
    opening_situation: str
    early_beats: list[str] = Field(min_length=2)
    likely_escalations: list[str] = Field(default_factory=list[str])


class SeedCharacter(SchemaModel):
    """A key character and motivation for the opening arc."""

    id: str
    name: str
    role: str
    motivation: str
    first_appearance: str


class CampaignSeed(SchemaModel):
    """Generated opening hooks and selected initial arc for a new campaign."""

    plot_hooks: list[PlotHook] = Field(min_length=3, max_length=5)
    selected_arc: SeedArc
    key_characters: list[SeedCharacter] = Field(min_length=1)
    initial_conflicts: list[str] = Field(min_length=1)
    opening_questions: list[str] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def _selected_hook_exists_and_ids_unique(self) -> CampaignSeed:
        hook_ids = [hook.id for hook in self.plot_hooks]
        if len(hook_ids) != len(set(hook_ids)):
            raise ValueError("plot_hooks ids must be unique")
        if self.selected_arc.selected_hook_id not in set(hook_ids):
            raise ValueError("selected_arc.selected_hook_id must refer to a plot hook")
        character_ids = [character.id for character in self.key_characters]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("key_characters ids must be unique")
        return self
