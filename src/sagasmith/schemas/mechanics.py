"""Mechanics schema models for PF2e first-slice contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import (
    AttackProfile,
    CombatantState,
    ConditionInstance,
    Effect,
    InitiativeEntry,
    InventoryItem,
    PositionTagValue,
    SchemaModel,
)
from .deltas import StateDelta


class CharacterSheet(SchemaModel):
    """Compact character sheet sufficient for the first level-1 PF2e slice."""

    id: str
    name: str
    level: int = Field(ge=1, le=20)
    ancestry: str
    background: str
    class_name: str
    abilities: dict[str, int]
    proficiencies: dict[str, Literal["untrained", "trained", "expert", "master", "legendary"]]
    max_hp: int = Field(gt=0)
    current_hp: int = Field(ge=0)
    armor_class: int = Field(gt=0)
    perception_modifier: int
    saving_throws: dict[str, int]
    skills: dict[str, int]
    attacks: list[AttackProfile]
    inventory: list[InventoryItem]
    conditions: list[ConditionInstance]

    @model_validator(mode="after")
    def _validate_hp_bounds(self) -> CharacterSheet:
        if self.current_hp > self.max_hp:
            raise ValueError(f"current_hp ({self.current_hp}) cannot exceed max_hp ({self.max_hp})")
        return self


class CombatState(SchemaModel):
    """Theater-of-mind combat state owned by deterministic rules services."""

    encounter_id: str
    round_number: int = Field(ge=1)
    active_combatant_id: str
    initiative_order: list[InitiativeEntry]
    combatants: list[CombatantState]
    positions: dict[str, PositionTagValue]
    action_counts: dict[str, int]
    reaction_available: dict[str, bool]


class CheckProposal(SchemaModel):
    """RulesLawyer proposal for a deterministic mechanical check."""

    id: str
    reason: str
    kind: Literal["skill", "attack", "save", "initiative", "flat"]
    actor_id: str
    target_id: str | None
    stat: str
    modifier: int
    dc: int | None
    secret: bool


class RollResult(SchemaModel):
    """Auditable deterministic die roll result."""

    roll_id: str
    seed: str
    die: str
    natural: int
    modifier: int
    total: int
    dc: int | None
    timestamp: str


class CheckResult(SchemaModel):
    """Resolved mechanical check with effects and replayable deltas."""

    proposal_id: str
    roll_result: RollResult
    degree: Literal["critical_success", "success", "failure", "critical_failure"]
    effects: list[Effect]
    state_deltas: list[StateDelta]
