"""Persistence schema models for SQLite trust records."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from sagasmith.schemas.common import SchemaModel


class CostLogRecord(SchemaModel):
    """Per-call cost accounting snapshot written to SQLite."""

    turn_id: str | None = None
    provider: Literal["openrouter", "fake"]
    model: str
    agent_name: str
    cost_usd: float = Field(ge=0)
    cost_is_approximate: bool
    tokens_prompt: int = Field(ge=0)
    tokens_completion: int = Field(ge=0)
    warnings_fired: list[Literal["70", "90"]]
    spent_usd_after: float = Field(ge=0)
    timestamp: str


class TurnRecord(SchemaModel):
    """Completed-turn record written during turn close.

    Status state machine::

        in_progress  --(orator complete)--> narrated
        narrated     --(turn_close)-------> complete
        in_progress  --(user /retry)------> retried  (then re-invoke for fresh attempt)
        in_progress  --(user /discard)----> discarded

    ``needs_vault_repair`` is the initial pre-close status used by the runtime
    and maps to "in_progress" in the state-machine above.
    """

    turn_id: str
    campaign_id: str
    session_id: str
    status: Literal[
        "complete",
        "needs_vault_repair",
        "narrated",
        "discarded",
        "retried",
        "retconned",
    ]
    started_at: str
    completed_at: str
    schema_version: int = Field(ge=1)
    sync_warning: str | None = None  # Set if player-vault sync fails post-commit


class CheckpointRef(SchemaModel):
    """Pointer to a LangGraph checkpoint payload."""

    checkpoint_id: str
    turn_id: str
    kind: Literal["pre_narration", "final"]
    created_at: str


class RetconAuditRecord(SchemaModel):
    """Audit record for a confirmed retcon that retains non-canonical rows."""

    retcon_id: str
    campaign_id: str
    selected_turn_id: str
    affected_turn_ids: list[str] = Field(min_length=1)
    prior_checkpoint_id: str
    confirmation_token: str
    reason: str
    created_at: str


class VaultWriteAuditRecord(SchemaModel):
    """Durable record of vault writes caused by a completed turn."""

    turn_id: str
    vault_path: str
    operation: str
    recorded_at: str


class TranscriptEntry(SchemaModel):
    """Append-only transcript line belonging to a turn."""

    turn_id: str
    kind: Literal["player_input", "narration_final", "system_note"]
    content: str
    sequence: int = Field(ge=0)
    created_at: str


class StateDeltaRecord(SchemaModel):
    """Persisted applied state delta."""

    turn_id: str
    delta_id: str
    source: Literal["rules", "oracle", "archivist", "safety", "user"]
    path: str
    operation: Literal["set", "increment", "append", "remove"]
    value_json: str
    reason: str
    applied_at: str


class SafetyEventRecord(SchemaModel):
    """SQLite-backed version of SafetyEvent, adds campaign_id + timestamp."""

    event_id: str
    campaign_id: str
    turn_id: str | None  # None when event is pre-gameplay (/pause during onboarding)
    kind: Literal[
        "pause",
        "line",
        "soft_limit_fade",
        "post_gate_rewrite",
        "fallback",
        "pre_gate_reroute",
        "pre_gate_block",
    ]
    policy_ref: str | None
    action_taken: str
    timestamp: str  # ISO 8601 UTC
    visibility: Literal["player_visible"] = (
        "player_visible"  # SAFE-06: Phase 3 events are ALL player-visible
    )


class AgentSkillLogRecord(SchemaModel):
    """Per-node activation log written by AgentActivationLogger."""

    turn_id: str = Field(min_length=1)
    agent_name: Literal["onboarding", "oracle", "rules_lawyer", "orator", "archivist"]
    skill_name: str | None = None
    started_at: str
    completed_at: str | None = None
    outcome: Literal["success", "interrupted", "error"]
