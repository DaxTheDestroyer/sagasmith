"""Compact LangGraph SagaState schema.

Added in Plan 04-01:
- pending_narration: list[str] — narration lines queued by the Orator node
  awaiting persistence at turn close.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .campaign_seed import CampaignSeed
from .common import SchemaModel
from .deltas import CanonConflict, StateDelta
from .mechanics import CharacterSheet, CheckResult, CombatState
from .narrative import MemoryPacket, SceneBrief, SessionState
from .player import ContentPolicy, HouseRules, PlayerProfile
from .safety_cost import CostState, SafetyEvent
from .world import WorldBible


class SagaState(SchemaModel):
    """Compact graph state with IDs/cursors instead of vault or transcript bodies."""

    campaign_id: str
    session_id: str
    turn_id: str
    phase: Literal["onboarding", "character_creation", "play", "combat", "paused", "session_end"]
    player_profile: PlayerProfile | None
    content_policy: ContentPolicy | None
    house_rules: HouseRules | None
    world_bible: WorldBible | None = None
    campaign_seed: CampaignSeed | None = None
    character_sheet: CharacterSheet | None
    session_state: SessionState
    combat_state: CombatState | None
    pending_player_input: str | None
    memory_packet: MemoryPacket | None
    scene_brief: SceneBrief | None
    resolved_beat_ids: list[str] = Field(default_factory=list[str])
    oracle_bypass_detected: bool = False
    check_results: list[CheckResult] = Field(default_factory=list[CheckResult])
    state_deltas: list[StateDelta] = Field(default_factory=list[StateDelta])
    pending_conflicts: list[CanonConflict] = Field(default_factory=list[CanonConflict])
    pending_narration: list[str] = Field(
        default_factory=list[str],
        description="Narration lines queued by the Orator node awaiting persistence at turn close.",
    )
    safety_events: list[SafetyEvent] = Field(default_factory=list[SafetyEvent])
    cost_state: CostState
    last_interrupt: dict[str, Any] | None = None
