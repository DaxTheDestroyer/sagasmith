"""Safety and cost accounting schema models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import SchemaModel


class SafetyEvent(SchemaModel):
    """Visible safety event emitted by safety controls or gates."""

    id: str
    turn_id: str
    kind: Literal["pause", "line", "soft_limit_fade", "post_gate_rewrite", "fallback"]
    policy_ref: str | None
    action_taken: str


class CostState(SchemaModel):
    """Session budget and usage state controlled by CostGovernor."""

    session_budget_usd: float = Field(ge=0)
    spent_usd_estimate: float = Field(ge=0)
    tokens_prompt: int = Field(ge=0)
    tokens_completion: int = Field(ge=0)
    unknown_cost_call_count: int = Field(default=0, ge=0)
    warnings_sent: list[Literal["70", "90"]]
    hard_stopped: bool
