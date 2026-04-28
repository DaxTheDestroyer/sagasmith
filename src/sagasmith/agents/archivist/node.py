"""Archivist agent node.

Phase 7 replaces with full turn-close-persistence + vault upsert skill per
archivist-skills.md §2.7.
"""

from __future__ import annotations

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet_stub,
)
from sagasmith.graph.activation_log import get_current_activation


def archivist_node(state, services):
    """Assemble a Phase 6 MemoryPacket, increment turn_count, and drain input."""
    if services._call_recorder is not None:
        services._call_recorder.append("archivist")
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None and store.find(name="memory-packet-assembly", agent_scope="archivist") is not None:
            activation.set_skill("memory-packet-assembly")
    session_state = dict(state["session_state"])
    session_state["turn_count"] = session_state["turn_count"] + 1
    memory_packet = assemble_memory_packet_stub(
        state,
        conn=getattr(services, "transcript_conn", None),
    )
    return {
        "session_state": session_state,
        "pending_player_input": None,
        "memory_packet": memory_packet.model_dump(),
        # Phase 4: pending_narration preserved so smoke test can sync to TUI.
        # Phase 7 archivist will persist to transcript_entries before clearing.
        "pending_narration": state.get("pending_narration", []),
    }
