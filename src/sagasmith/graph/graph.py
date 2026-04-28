"""StateGraph construction for SagaSmith."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from sagasmith.graph.routing import route_after_oracle, route_by_phase
from sagasmith.graph.state import SagaGraphState


def build_saga_graph(bootstrap: Any) -> Any:
    """Build and compile a StateGraph with five named agent nodes."""
    g = StateGraph(SagaGraphState)
    g.add_node("onboarding", bootstrap.onboarding)
    g.add_node("oracle", bootstrap.oracle)
    g.add_node("rules_lawyer", bootstrap.rules_lawyer)
    g.add_node("orator", bootstrap.orator)
    g.add_node("archivist", bootstrap.archivist)

    # Phase-driven conditional START edge
    g.add_conditional_edges(
        START,
        route_by_phase,
        {
            "onboarding": "onboarding",
            "oracle": "oracle",
            "rules_lawyer": "rules_lawyer",
            END: END,
        },
    )
    # Play chain
    g.add_conditional_edges("oracle", route_after_oracle, {"rules_lawyer": "rules_lawyer", END: END})
    g.add_edge("rules_lawyer", "orator")
    g.add_edge("orator", "archivist")
    g.add_edge("archivist", END)
    # Onboarding exit
    g.add_edge("onboarding", END)

    return g.compile()  # NO checkpointer; Plan 04-02 adds build_persistent_graph.
