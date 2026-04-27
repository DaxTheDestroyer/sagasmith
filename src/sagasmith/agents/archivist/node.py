"""Archivist agent node.

Phase 7 replaces with full turn-close-persistence + vault upsert skill per
archivist-skills.md §2.7.
"""

from __future__ import annotations


def archivist_node(state, services):
    """Increment turn_count, drain pending input and narration."""
    if services._call_recorder is not None:
        services._call_recorder.append("archivist")
    session_state = dict(state["session_state"])
    session_state["turn_count"] = session_state["turn_count"] + 1
    return {
        "session_state": session_state,
        "pending_player_input": None,
        "pending_narration": [],
    }
