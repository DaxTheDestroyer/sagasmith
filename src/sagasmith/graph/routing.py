"""Phase-driven routing for the SagaSmith StateGraph.

Phase 5 routes combat through RulesLawyer first-slice mechanics before
returning completed encounters to play.
"""

from __future__ import annotations

from langgraph.graph import END

from sagasmith.graph.state import SagaGraphState
from sagasmith.schemas.enums import Phase

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
    return PHASE_TO_ENTRY[state["phase"]]
