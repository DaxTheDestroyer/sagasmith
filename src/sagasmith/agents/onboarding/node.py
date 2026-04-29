"""Onboarding agent node.

Phase 5 replaces the self-loop signal with real character creation per
onboarding-skills.md §2.
"""

from __future__ import annotations

from sagasmith.graph.activation_log import get_current_activation


def onboarding_node(state, services):
    """Return self-loop signal until profile/policy/rules are present."""
    if services._call_recorder is not None:
        services._call_recorder.append("onboarding")
    if (
        state["player_profile"] is None
        or state["content_policy"] is None
        or state["house_rules"] is None
    ):
        activation = get_current_activation()
        if activation is not None:
            store = services.skill_store
            if (
                store is not None
                and store.find(name="onboarding-phase-wizard", agent_scope="onboarding") is not None
            ):
                activation.set_skill("onboarding-phase-wizard")
        return {"phase": "onboarding"}
    return {}
