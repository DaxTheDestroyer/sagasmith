"""Graph bootstrap: assemble agent nodes and compiled graph from services."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


@dataclass(frozen=True)
class AgentServices:
    """Runtime services bundle injected into every agent node."""

    dice: DiceService
    cost: CostGovernor
    safety: object | None = None
    llm: object | None = None
    # test-only hook: if non-None, nodes append their name to this list on entry.
    # Used by graph tests to verify execution order without polluting production code.
    _call_recorder: list[str] | None = None


@dataclass(frozen=True)
class GraphBootstrap:
    """Holds bound node callables and the services bundle."""

    services: AgentServices
    onboarding: object
    oracle: object
    rules_lawyer: object
    orator: object
    archivist: object

    @classmethod
    def from_services(
        cls,
        *,
        dice: DiceService,
        cost: CostGovernor,
        safety: object | None = None,
        llm: object | None = None,
        _call_recorder: list[str] | None = None,
    ) -> GraphBootstrap:
        services = AgentServices(
            dice=dice,
            cost=cost,
            safety=safety,
            llm=llm,
            _call_recorder=_call_recorder,
        )
        from sagasmith.agents.archivist.node import archivist_node
        from sagasmith.agents.onboarding.node import onboarding_node
        from sagasmith.agents.oracle.node import oracle_node
        from sagasmith.agents.orator.node import orator_node
        from sagasmith.agents.rules_lawyer.node import rules_lawyer_node

        return cls(
            services=services,
            onboarding=functools.partial(onboarding_node, services=services),
            oracle=functools.partial(oracle_node, services=services),
            rules_lawyer=functools.partial(rules_lawyer_node, services=services),
            orator=functools.partial(orator_node, services=services),
            archivist=functools.partial(archivist_node, services=services),
        )


def build_default_graph(bootstrap: GraphBootstrap) -> Any:
    """Return a compiled StateGraph from a bootstrap bundle."""
    from sagasmith.graph.graph import build_saga_graph

    return build_saga_graph(bootstrap)
