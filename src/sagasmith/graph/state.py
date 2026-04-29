"""LangGraph TypedDict mirror of SagaState.

Rationale: LangGraph StateGraph accepts TypedDict containers. Keeping
SagaState (Pydantic) canonical and re-exporting a TypedDict mirror keeps
validation at persistence boundaries without paying Pydantic cost on every
node transition. Import-time field-drift guard prevents silent regressions.
"""

from __future__ import annotations

from typing import Any, TypedDict

from sagasmith.schemas.saga_state import SagaState


class SagaGraphState(TypedDict):
    campaign_id: str
    session_id: str
    turn_id: str
    phase: str  # one of Phase enum values; TypedDict uses str for compatibility
    player_profile: object | None
    content_policy: object | None
    house_rules: object | None
    world_bible: object | None
    campaign_seed: object | None
    character_sheet: object | None
    session_state: object
    combat_state: object | None
    pending_player_input: str | None
    memory_packet: object | None
    scene_brief: object | None
    resolved_beat_ids: list[str]
    oracle_bypass_detected: bool
    check_results: list[object]
    state_deltas: list[object]
    pending_conflicts: list[object]
    pending_narration: list[str]
    safety_events: list[object]
    cost_state: object
    last_interrupt: dict[str, Any] | None
    vault_master_path: str
    vault_player_path: str
    rolling_summary: str | None


# Import-time field-drift guard
_pydantic_fields = set(SagaState.model_fields.keys())
_typeddict_fields = set(SagaGraphState.__annotations__.keys())
if _pydantic_fields != _typeddict_fields:
    missing_from_td = _pydantic_fields - _typeddict_fields
    extra_in_td = _typeddict_fields - _pydantic_fields
    raise RuntimeError(
        f"SagaGraphState drift detected. "
        f"Missing from TypedDict: {missing_from_td}; "
        f"Extra in TypedDict: {extra_in_td}"
    )


def from_saga_state(model: SagaState) -> SagaGraphState:
    return model.model_dump()  # type: ignore[return-value]


def to_saga_state(data: SagaGraphState) -> SagaState:
    return SagaState.model_validate(data)
