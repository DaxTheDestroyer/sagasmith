"""Archivist agent node — thin Adapter over the Turn Plan Module.

Owns: skill-activation logging and LangGraph state projection.
Planning logic lives in sagasmith.turn_plan.build_turn_plan.
"""

from __future__ import annotations

from typing import Any

from sagasmith.graph.activation_log import get_current_activation
from sagasmith.vault import VaultPage

_ARCHIVIST_SKILLS = (
    "entity-resolution",
    "vault-page-upsert",
    "visibility-promotion",
    "rolling-summary-update",
    "session-page-authoring",
    "canon-conflict-detection",
    "memory-packet-assembly",
)


def archivist_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Project the Archivist Turn Plan onto a LangGraph-compatible state delta."""
    # Lazy import breaks the turn_plan → agents.archivist → node → turn_plan cycle.
    from sagasmith.turn_plan import TurnPlanContext, build_turn_plan

    if getattr(services, "_call_recorder", None) is not None:
        services._call_recorder.append("archivist")
    _log_skill_activations(services)

    plan = build_turn_plan(
        TurnPlanContext(
            state=state,
            vault_service=getattr(services, "vault_service", None),
            transcript_conn=getattr(services, "transcript_conn", None),
            llm=getattr(services, "llm", None),
        )
    )

    # LangGraph's msgpack serializer cannot handle VaultPage objects when a
    # transcript_conn is present (checkpoint path). Flatten to dicts; the
    # runtime reconstructs VaultPage instances after the graph completes.
    if getattr(services, "transcript_conn", None) is None:
        pending: list[VaultPage] | list[dict[str, Any]] = list(plan.pending_vault_writes)
    else:
        pending = [
            {"frontmatter": p.frontmatter.model_dump(mode="json"), "body": p.body}
            for p in plan.pending_vault_writes
        ]

    return {
        "session_state": dict(plan.session_state),
        "rolling_summary": plan.rolling_summary,
        "pending_conflicts": list(plan.pending_conflicts),
        "pending_player_input": None,
        "memory_packet": plan.memory_packet.model_dump(),
        "vault_pending_writes": pending,
        # Phase 7 archivist will persist to transcript_entries before clearing.
        "pending_narration": list(plan.pending_narration),
    }


def _log_skill_activations(services: Any) -> None:
    activation = get_current_activation()
    if activation is None:
        return
    store = services.skill_store if hasattr(services, "skill_store") else None
    if store is None:
        return
    for name in _ARCHIVIST_SKILLS:
        if store.find(name=name, agent_scope="archivist") is not None:
            activation.set_skill(name)
