"""Orator agent node.

Phase 6 replaces stub with streaming narration through LLMClient +
safety post-gate.

Plan 06-07: Integrates SafetyPostGate for post-generation content scanning.
Two-rewrite limit enforcement is deferred to the real Orator pipeline (06-04);
this stub applies the post-gate once and uses fallback narration on block.
"""

from __future__ import annotations

from typing import Any

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet_stub,
)
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.safety_cost import SafetyEvent
from sagasmith.services.safety_post_gate import (
    BlockFallback,
    Rewrite,
    SafetyPostGate,
)

_FIRST_SLICE_NARRATION = "You take a moment to assess the scene."
_FALLBACK_NARRATION = "The scene shifts. A new detail draws your attention."


def orator_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Ensure memory context, then append one fixed narration line when scene_brief is present.

    Plan 06-07: Post-gate safety scanning runs on generated narration before
    it enters ``pending_narration``.  On block, fallback narration is used.
    """
    if services._call_recorder is not None:
        services._call_recorder.append("orator")
    updates: dict[str, Any] = {}
    if state.get("memory_packet") is None:
        memory_packet = assemble_memory_packet_stub(
            state,
            conn=getattr(services, "transcript_conn", None),
        )
        updates["memory_packet"] = memory_packet.model_dump()
    activation = get_current_activation()
    if activation is not None:
        activation.set_skill("scene-rendering")
    if state["scene_brief"] is not None:
        narration = _FIRST_SLICE_NARRATION
        # Post-gate safety scan (Plan 06-07)
        narration, safety_events = _apply_post_gate(
            narration=narration,
            state=state,
            services=services,
        )
        updates["pending_narration"] = state["pending_narration"] + [narration]
        if safety_events:
            updates["safety_events"] = [*state.get("safety_events", []), *safety_events]
    return updates


def _apply_post_gate(
    *,
    narration: str,
    state: dict[str, Any],
    services: Any,
) -> tuple[str, list[dict[str, Any]]]:
    """Run post-gate safety scan on narration.

    Returns (final_narration, list_of_safety_event_dicts).
    """
    content_policy = state.get("content_policy")
    if content_policy is None:
        return narration, []

    llm_client = getattr(services, "llm", None)
    cheap_model = "fake-cheap"
    # Try to extract cheap_model from provider config if available
    provider_config = state.get("provider_config")
    if provider_config is not None:
        cheap_model = getattr(provider_config, "cheap_model", cheap_model)
        if isinstance(provider_config, dict):
            cheap_model = provider_config.get("cheap_model", cheap_model)

    gate = SafetyPostGate(llm_client=llm_client, cheap_model=cheap_model)
    verdict = gate.scan(narration, content_policy)

    events: list[dict[str, Any]] = []
    turn_id = str(state.get("turn_id") or "unknown")

    if isinstance(verdict, BlockFallback):
        # Log and use fallback narration
        _log_post_gate_event(services, state, "fallback", verdict.violated_term, verdict.reason or "blocked")
        events.append(
            SafetyEvent(
                id=f"safety_{turn_id}_post_gate_block",
                turn_id=turn_id,
                kind="fallback",
                policy_ref=verdict.violated_term,
                action_taken=f"fallback:{verdict.reason or 'blocked'}"[:200],
            ).model_dump()
        )
        return _FALLBACK_NARRATION, events

    if isinstance(verdict, Rewrite):
        # Log the rewrite; in the stub, we accept the narration as-is
        # (real Orator 06-04 will re-invoke LLM)
        _log_post_gate_event(services, state, "post_gate_rewrite", verdict.violated_term, verdict.reason or "rewrite")
        events.append(
            SafetyEvent(
                id=f"safety_{turn_id}_post_gate_rewrite",
                turn_id=turn_id,
                kind="post_gate_rewrite",
                policy_ref=verdict.violated_term,
                action_taken=f"rewrite:{verdict.reason or 'rewrite'}"[:200],
            ).model_dump()
        )
        # For the stub, use fallback on rewrite to avoid showing flagged content
        return _FALLBACK_NARRATION, events

    # Pass — narration is safe
    return narration, []


def _log_post_gate_event(
    services: Any,
    state: dict[str, Any],
    event_kind: str,
    policy_ref: str | None,
    reason: str,
) -> None:
    """Log a post-gate event via SafetyEventService (SQLite) when available."""
    safety_svc = getattr(services, "safety", None)
    if safety_svc is None:
        return
    campaign_id = state.get("campaign_id", "")
    turn_id = state.get("turn_id")
    try:
        if event_kind == "fallback":
            safety_svc.log_fallback(
                campaign_id=campaign_id,
                reason=reason,
                turn_id=turn_id,
            )
        elif event_kind == "post_gate_rewrite":
            safety_svc.log_post_gate_rewrite(
                campaign_id=campaign_id,
                policy_ref=policy_ref,
                reason=reason,
                turn_id=turn_id,
            )
    except Exception:
        try:
            safety_svc.conn.rollback()
        except Exception:
            pass
