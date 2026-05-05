"""Rules Lawyer agent node: thin Adapter over Rules Turn Resolution."""

from __future__ import annotations

from typing import Any

from sagasmith.graph.activation_log import get_current_activation
from sagasmith.rules_turn_resolution import RulesTurnContext, resolve_rules_turn


def rules_lawyer_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Project one Rules Turn Resolution result onto LangGraph state updates."""

    if getattr(services, "_call_recorder", None) is not None:
        services._call_recorder.append("rules_lawyer")

    result = resolve_rules_turn(
        RulesTurnContext(
            state=state,
            dice=services.dice,
            cost=getattr(services, "cost", None),
            llm=getattr(services, "llm", None),
            provider_config=getattr(services, "provider_config", None),
            skill_store=getattr(services, "skill_store", None),
        )
    )

    activation = get_current_activation()
    if activation is not None:
        for skill in result.skills_activated:
            activation.set_skill(skill)

    return dict(result.state_updates)
