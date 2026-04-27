"""Orator agent node.

Phase 6 replaces stub with streaming narration through LLMClient +
safety post-gate.
"""

from __future__ import annotations

from sagasmith.graph.activation_log import get_current_activation

_FIRST_SLICE_NARRATION = "You take a moment to assess the scene."


def orator_node(state, services):
    """Append one fixed narration line when scene_brief is present."""
    if services._call_recorder is not None:
        services._call_recorder.append("orator")
    activation = get_current_activation()
    if activation is not None:
        activation.set_skill("scene-rendering")
    if state["scene_brief"] is not None:
        return {"pending_narration": state["pending_narration"] + [_FIRST_SLICE_NARRATION]}
    return {}
