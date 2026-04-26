"""Player onboarding and preference schema models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import BudgetPolicy, SchemaModel, require_exact_keys

Pillar = Literal["combat", "exploration", "social", "puzzle"]
DiceUx = Literal["auto", "reveal", "hidden"]


class PlayerProfile(SchemaModel):
    """Persisted player preference contract produced during onboarding."""

    genre: list[str]
    tone: list[str]
    touchstones: list[str]
    pillar_weights: dict[str, float]
    pacing: Literal["slow", "medium", "fast"]
    combat_style: Literal["theater_of_mind"]
    dice_ux: DiceUx
    campaign_length: Literal["one_shot", "arc", "open_ended"]
    character_mode: Literal["guided", "player_led", "pregenerated"]
    death_policy: Literal["hardcore", "heroic_recovery", "retire_and_continue"]
    budget: BudgetPolicy

    @model_validator(mode="after")
    def _pillar_weights_valid(self) -> PlayerProfile:
        required = {"combat", "exploration", "social", "puzzle"}
        require_exact_keys(self.pillar_weights, required, "pillar_weights")
        total = sum(self.pillar_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"pillar_weights must sum to 1.0 within 0.01, got {total}")
        return self


class ContentPolicy(SchemaModel):
    """Player safety policy for hard limits, soft limits, and preferences."""

    hard_limits: list[str]
    soft_limits: dict[str, Literal["fade_to_black", "avoid_detail", "ask_first"]]
    preferences: list[str]


class HouseRules(SchemaModel):
    """Campaign-level house rules locked before gameplay starts."""

    dice_ux: DiceUx
    initiative_visible: bool
    allow_retcon: bool
    auto_save_every_turn: bool
    session_end_trigger: Literal["player_command_or_budget"] = Field(
        description="Only player command or budget exhaustion can end an MVP session."
    )
