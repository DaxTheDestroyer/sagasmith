"""Archivist agent node.

Phase 7 replaces with full turn-close-persistence + vault upsert skill per
archivist-skills.md §2.7.
"""

from __future__ import annotations

from sagasmith.graph.activation_log import get_current_activation


def archivist_node(state, services):
    """Increment turn_count, drain pending input and narration."""
    if services._call_recorder is not None:
        services._call_recorder.append("archivist")
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None and store.find(name="turn-close-persistence", agent_scope="archivist") is not None:
            activation.set_skill("turn-close-persistence")
    session_state = dict(state["session_state"])
    session_state["turn_count"] = session_state["turn_count"] + 1
    return {
        "session_state": session_state,
        "pending_player_input": None,
        # Phase 4: pending_narration preserved so smoke test can sync to TUI.
        # Phase 7 archivist will persist to transcript_entries before clearing.
        "pending_narration": state.get("pending_narration", []),
    }
