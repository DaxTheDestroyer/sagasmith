"""Phase-driven routing for the SagaSmith StateGraph.

Phase 5 routes combat through RulesLawyer first-slice mechanics before
returning completed encounters to play.
"""

from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END

from sagasmith.agents.oracle.skills.player_choice_branching.logic import analyze_player_choice
from sagasmith.graph.state import SagaGraphState
from sagasmith.schemas.enums import Phase
from sagasmith.schemas.narrative import SceneBrief

# END is a langgraph sentinel (not a str). We use object to keep types honest
# at runtime; pyright treats END as its opaque sentinel type.
PHASE_TO_ENTRY: dict[str, object] = {
    Phase.ONBOARDING.value: "onboarding",
    Phase.CHARACTER_CREATION.value: "onboarding",  # Phase 5 will split
    Phase.PLAY.value: "oracle",
    Phase.COMBAT.value: "rules_lawyer",
    Phase.PAUSED.value: END,
    Phase.SESSION_END.value: END,
}

# Import-time exhaustiveness guard
_enum_values = {p.value for p in Phase}
_routed_values = set(PHASE_TO_ENTRY.keys())
if _enum_values != _routed_values:
    missing = _enum_values - _routed_values
    raise RuntimeError(
        f"PHASE_TO_ENTRY missing routes for Phase values: {missing}. "
        f"Add a route (node name or END) for every phase."
    )


def route_by_phase(state: SagaGraphState) -> object:
    if state["phase"] == Phase.PLAY.value and not should_route_to_oracle(state):
        return "rules_lawyer"
    return PHASE_TO_ENTRY[state["phase"]]


def should_route_to_oracle(state: SagaGraphState) -> bool:
    """Return True when Oracle must plan or re-plan the active scene."""

    if state["phase"] != Phase.PLAY.value:
        return False
    payload = state.get("scene_brief")
    if payload is None:
        return True
    if bool(state.get("oracle_bypass_detected")):
        return True
    try:
        brief = SceneBrief.model_validate(payload)
    except Exception:
        return True
    branch = analyze_player_choice(
        player_input=state.get("pending_player_input"),
        prior_scene_brief=brief,
        memory_packet=cast(Any, state.get("memory_packet")),
    )
    if branch.bypass_detected:
        return True
    return bool(brief.beat_ids) and set(state.get("resolved_beat_ids", [])) >= set(brief.beat_ids)


def route_after_oracle(state: SagaGraphState) -> object:
    """Halt when Oracle posts a pre-generation interrupt, otherwise continue."""

    interrupt = state.get("last_interrupt")
    if isinstance(interrupt, dict) and interrupt.get("kind") in {"budget_stop", "safety_block"}:
        return END
    return "rules_lawyer"
