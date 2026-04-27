"""Onboarding agent node.

Phase 5 replaces the self-loop signal with real character creation per
onboarding-skills.md §2.
"""

from __future__ import annotations


def onboarding_node(state, services):
    """Return self-loop signal until profile/policy/rules are present."""
    if services._call_recorder is not None:
        services._call_recorder.append("onboarding")
    if (
        state["player_profile"] is None
        or state["content_policy"] is None
        or state["house_rules"] is None
    ):
        return {"phase": "onboarding"}
    return {}
