"""Shared helpers and small value objects for SagaSmith schemas.

Interpretation choices for STATE_SCHEMA.md shapes that were intentionally compact:
- ``GameClock`` is day/hour/minute because the first slice only needs a readable
  in-world clock for status display and duration math hooks.
- ``PacingTarget`` stores the narrative pillar, tension, and expected beat length
  used by Oracle/Orator without adding a separate pacing taxonomy yet.
- ``AttackProfile`` is a minimal auditable attack record: id/name/modifier/damage,
  traits, and optional range.
- ``Effect`` is a typed description plus optional target for mechanics outcomes;
  deterministic services will refine effect semantics in later rules plans.
- ``MemoryPacket`` token estimates use ``ceil(len(text) / 4)`` via integer math.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PositionTagValue = Literal["close", "near", "far", "behind_cover"]


class SchemaModel(BaseModel):
    """Fail-closed base class for all schema contracts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=False)


class BudgetPolicy(SchemaModel):
    """Player-configured per-session budget policy."""

    per_session_usd: float = Field(ge=0)
    hard_stop: bool


class GameClock(SchemaModel):
    """Minimal in-game clock: day number plus 24-hour hour/minute."""

    day: int = Field(ge=1)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)


class PacingTarget(SchemaModel):
    """Compact pacing instruction for a planned scene."""

    pillar: Literal["combat", "exploration", "social", "puzzle"]
    tension: str
    length: Literal["short", "medium", "long"]


class MechanicalTrigger(SchemaModel):
    """Potential deterministic-mechanics handoff requested by Oracle."""

    kind: Literal["skill", "attack", "save", "initiative", "flat"]
    reason: str
    stat: str | None = None
    dc: int | None = None


class MemoryEntityRef(SchemaModel):
    """Reference to a vault-backed or explicitly provisional memory entity."""

    entity_id: str
    kind: str
    name: str
    vault_path: str | None
    provisional: bool = False


class AttackProfile(SchemaModel):
    """Minimal attack option for a first-slice character or combatant."""

    id: str
    name: str
    modifier: int
    damage: str
    traits: list[str] = Field(default_factory=list)
    range: str | None = None


class InventoryItem(SchemaModel):
    """Compact inventory item carried on a character sheet."""

    id: str
    name: str
    quantity: int = Field(ge=0)
    bulk: float = Field(ge=0)


class ConditionInstance(SchemaModel):
    """Condition marker; first slice permits an empty list but keeps the shape."""

    id: str
    name: str
    value: int | None = None
    expires_at: str | None = None


class InitiativeEntry(SchemaModel):
    """Single entry in a deterministic initiative order."""

    combatant_id: str
    initiative: int


class CombatantState(SchemaModel):
    """Runtime combatant state used inside CombatState."""

    id: str
    name: str
    current_hp: int = Field(ge=0)
    max_hp: int = Field(gt=0)
    armor_class: int = Field(gt=0)
    conditions: list[ConditionInstance] = Field(default_factory=list[ConditionInstance])

    @model_validator(mode="after")
    def _validate_hp_bounds(self) -> CombatantState:
        if self.current_hp > self.max_hp:
            raise ValueError(f"current_hp ({self.current_hp}) cannot exceed max_hp ({self.max_hp})")
        return self


class Effect(SchemaModel):
    """Human-readable mechanics effect with optional target reference."""

    kind: str
    description: str
    target_id: str | None = None


def estimate_tokens(text: str) -> int:
    """Return a cheap token estimate using ceil(len(text) / 4)."""

    return (len(text) + 3) // 4


def require_exact_keys(value: Mapping[str, object], required: set[str], field_name: str) -> None:
    """Raise ValueError unless a dict has exactly the required keys."""

    actual = set(value)
    if actual != required:
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        raise ValueError(
            f"{field_name} must have exactly keys {sorted(required)}; "
            f"missing={missing}, extra={extra}"
        )
