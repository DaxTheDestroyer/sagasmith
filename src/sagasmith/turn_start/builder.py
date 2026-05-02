"""Turn Start: construct the LangGraph state dict for a new play turn.

Owns: turn-id progression, phase selection, first-slice character seeding,
cost-state shape, combat carryover, and narration/check-result carryover.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sagasmith.graph.state import SagaGraphState


@dataclass(frozen=True)
class TurnStartContext:
    """Everything the builder needs to construct the next turn's starting state."""

    campaign_id: str
    session_id: str
    session_number: int
    current_turn_id: str | None  # None on the very first turn
    session_budget_usd: float  # extracted from CostGovernor by caller
    snapshot_values: Mapping[str, Any] | None  # graph.get_state(...).values, or None


@dataclass(frozen=True)
class TurnStart:
    """Result of build_turn_start: a ready-to-invoke state dict and the new turn id."""

    state: SagaGraphState  # ready to pass to GraphRuntime.invoke_turn
    next_turn_id: str  # already-bumped id; caller assigns to current_turn_id


def build_turn_start(context: TurnStartContext, player_input: str) -> TurnStart:
    """Build the starting state for the next play turn.

    Pure function: no I/O. All inputs come from the caller; no side effects.
    """
    from sagasmith.rules.first_slice import make_first_slice_character

    snapshot: Mapping[str, Any] = context.snapshot_values or {}

    # Turn-id progression: bump from snapshot's last turn_id if snapshot is present.
    # Without a snapshot (first turn or empty thread) use current_turn_id directly.
    if context.snapshot_values:
        base = str(snapshot.get("turn_id") or context.current_turn_id or "turn_000000")
        next_turn_id = _next_turn_id(base)
    else:
        next_turn_id = context.current_turn_id or "turn_000001"

    existing_combat = snapshot.get("combat_state")
    existing_sheet = snapshot.get("character_sheet")
    existing_checks: list[Any] = list(snapshot.get("check_results") or [])
    existing_deltas: list[Any] = list(snapshot.get("state_deltas") or [])
    existing_narration: list[str] = list(snapshot.get("pending_narration") or [])

    phase = "combat" if existing_combat is not None else "play"
    character_sheet = (
        existing_sheet if existing_sheet is not None else make_first_slice_character().model_dump()
    )

    state: SagaGraphState = {  # type: ignore[assignment]
        "campaign_id": context.campaign_id,
        "session_id": context.session_id,
        "turn_id": next_turn_id,
        "phase": phase,
        "player_profile": None,
        "content_policy": None,
        "house_rules": None,
        "world_bible": None,
        "campaign_seed": None,
        "character_sheet": character_sheet,
        "session_state": {
            "current_scene_id": None,
            "current_location_id": None,
            "active_quest_ids": [],
            "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
            "turn_count": 0,
            "transcript_cursor": None,
            "last_checkpoint_id": None,
            "session_number": context.session_number,
        },
        "combat_state": existing_combat,
        "pending_player_input": player_input,
        "memory_packet": None,
        "scene_brief": None,
        "resolved_beat_ids": list(snapshot.get("resolved_beat_ids") or []),
        "oracle_bypass_detected": False,
        "check_results": existing_checks,
        "state_deltas": existing_deltas,
        "pending_conflicts": [],
        "pending_narration": existing_narration,
        "safety_events": [],
        "cost_state": {
            "session_budget_usd": context.session_budget_usd,
            "spent_usd_estimate": 0.0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "unknown_cost_call_count": 0,
            "warnings_sent": [],
            "hard_stopped": False,
        },
        "last_interrupt": None,
        "vault_master_path": str(snapshot.get("vault_master_path") or ""),
        "vault_player_path": str(snapshot.get("vault_player_path") or ""),
        "rolling_summary": snapshot.get("rolling_summary"),
        "vault_pending_writes": [],
    }

    return TurnStart(state=state, next_turn_id=next_turn_id)


def _next_turn_id(turn_id: str) -> str:
    prefix, sep, suffix = turn_id.rpartition("_")
    if sep and suffix.isdigit():
        return f"{prefix}_{int(suffix) + 1:0{len(suffix)}d}"
    return f"{turn_id}_next"
