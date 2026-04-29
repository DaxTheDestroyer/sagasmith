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
from .mechanics import CharacterSheet, CombatState
from .narrative import MemoryPacket, SceneBrief, SessionState
from .player import ContentPolicy, HouseRules, PlayerProfile
from .safety_cost import CostState
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
    check_results: list[Any] = Field(default_factory=list)
    state_deltas: list[Any] = Field(default_factory=list)
    pending_conflicts: list[Any] = Field(default_factory=list)
    pending_narration: list[str] = Field(
        default_factory=list,
        description="Narration lines queued by the Orator node awaiting persistence at turn close.",
    )
    safety_events: list[Any] = Field(default_factory=list)
    cost_state: CostState
    last_interrupt: dict[str, Any] | None = None
    vault_master_path: str
    vault_player_path: str
    rolling_summary: str | None = None
    # Transient: pages produced by the Archivist this turn; consumed by close_turn and not persisted.
    vault_pending_writes: list[Any] = Field(default_factory=list)
