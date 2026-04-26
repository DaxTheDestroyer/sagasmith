"""Narrative and memory schema models."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import (
    GameClock,
    MechanicalTrigger,
    MemoryEntityRef,
    PacingTarget,
    SchemaModel,
    estimate_tokens,
)


class SessionState(SchemaModel):
    """Compact session cursor state; transcript/checkpoint references are IDs."""

    current_scene_id: str | None
    current_location_id: str | None
    active_quest_ids: list[str]
    in_game_clock: GameClock
    turn_count: int = Field(ge=0)
    transcript_cursor: str | None
    last_checkpoint_id: str | None


class SceneBrief(SchemaModel):
    """Oracle scene plan consumed by Orator; never player-facing narration."""

    scene_id: str
    intent: str
    location: str | None
    present_entities: list[str]
    beats: list[str]
    success_outs: list[str]
    failure_outs: list[str]
    pacing_target: PacingTarget
    callbacks_seeded: list[str] = Field(default_factory=list[str])
    callbacks_payoff_candidates: list[str] = Field(default_factory=list[str])
    mechanical_triggers: list[MechanicalTrigger] = Field(default_factory=list[MechanicalTrigger])
    content_warnings: list[str] = Field(default_factory=list[str])


class MemoryPacket(SchemaModel):
    """Bounded campaign memory context.

    Token usage is estimated with the deliberately cheap heuristic
    ``ceil(len(text) / 4)`` over ``summary`` plus every ``recent_turns`` entry.
    Later retrieval work may use a tokenizer, but this fail-closed contract keeps
    long-context dumps out of graph state now.
    """

    token_cap: int = Field(gt=0)
    summary: str
    entities: list[MemoryEntityRef]
    recent_turns: list[str]
    open_callbacks: list[str]
    retrieval_notes: list[str]

    @model_validator(mode="after")
    def _token_cap_holds(self) -> MemoryPacket:
        estimated = estimate_tokens(self.summary) + sum(estimate_tokens(turn) for turn in self.recent_turns)
        if estimated > self.token_cap:
            raise ValueError(
                f"MemoryPacket estimated tokens {estimated} exceed token_cap {self.token_cap}"
            )
        return self
