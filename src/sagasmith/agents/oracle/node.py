"""Oracle agent node — thin Adapter over the Scene Planning Module.

Owns: skill-activation logging, InterruptEnvelope construction, and
LangGraph state projection. Planning logic lives in
sagasmith.scene_planning.plan_scene.
"""

from __future__ import annotations

from typing import Any

from sagasmith.graph.interrupts import InterruptEnvelope, InterruptKind


def oracle_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Project the Oracle Scene Plan onto a LangGraph-compatible state delta."""
    # Lazy import breaks the scene_planning → agents.oracle → node → scene_planning cycle.
    from sagasmith.scene_planning import ScenePlanContext, plan_scene

    if getattr(services, "_call_recorder", None) is not None:
        services._call_recorder.append("oracle")

    plan = plan_scene(
        ScenePlanContext(
            state=state,
            llm=getattr(services, "llm", None),
            cost=getattr(services, "cost", None),
            safety=getattr(services, "safety", None),
            skill_execution=services.skills_for("oracle"),
            transcript_conn=getattr(services, "transcript_conn", None),
            vault_service=getattr(services, "vault_service", None),
            provider_config=getattr(services, "provider_config", None),
        )
    )

    delta: dict[str, Any] = dict(plan.state_updates)

    if plan.pre_gate_events:
        delta["safety_events"] = [
            *state.get("safety_events", []),
            *(event.model_dump() for event in plan.pre_gate_events),
        ]

    if plan.interrupt is not None:
        delta["last_interrupt"] = InterruptEnvelope.build(
            kind=InterruptKind(plan.interrupt.kind),
            payload={"reason": plan.interrupt.reason},
            thread_id=f"campaign:{state.get('campaign_id', 'unknown')}",
        ).model_dump()

    return delta
