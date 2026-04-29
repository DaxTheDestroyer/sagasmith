"""Oracle agent node.

Phase 6 replaces the stub with scene-brief-composition skill per
oracle-skills.md §2.3.
"""

from __future__ import annotations

import contextlib
from typing import Any, cast

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
    assemble_memory_packet_stub,
)
from sagasmith.agents.oracle.skills.campaign_seed_generation.logic import generate_campaign_seed
from sagasmith.agents.oracle.skills.content_policy_routing.logic import (
    Blocked,
    Rerouted,
    safety_pre_gate,
)
from sagasmith.agents.oracle.skills.player_choice_branching.logic import analyze_player_choice
from sagasmith.agents.oracle.skills.scene_brief_composition.logic import compose_scene_brief
from sagasmith.agents.oracle.skills.world_bible_generation.logic import generate_world_bible
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.graph.bootstrap import AgentServices
from sagasmith.graph.interrupts import InterruptEnvelope, InterruptKind
from sagasmith.providers import LLMClient
from sagasmith.schemas.narrative import SceneBrief
from sagasmith.schemas.safety_cost import SafetyEvent
from sagasmith.schemas.world import WorldBible
from sagasmith.services.errors import BudgetStopError as _BudgetStop

_FIRST_SLICE_STUB_SCENE_BRIEF = SceneBrief(
    scene_id="scene_stub_001",
    intent="placeholder first-slice scene (replaced in Phase 6)",
    location=None,
    present_entities=[],
    beats=[],
    beat_ids=[],
    success_outs=[],
    failure_outs=[],
    pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
)


def oracle_node(state: dict[str, Any], services: AgentServices) -> dict[str, Any]:
    """Generate one-shot campaign context, ensure memory, then plan the scene stub."""
    call_recorder = getattr(services, "_call_recorder", None)
    if call_recorder is not None:
        call_recorder.append("oracle")
    updates: dict[str, Any] = {}
    activation = get_current_activation()
    if _should_generate_campaign_context(state, services):
        _set_skill_if_available(activation, services, "world-bible-generation")
        world_bible_payload = state.get("world_bible")
        if world_bible_payload is None:
            world_bible = generate_world_bible(
                player_profile=state["player_profile"],
                content_policy=state["content_policy"],
                house_rules=state["house_rules"],
                llm_client=cast(LLMClient, services.llm),
                turn_id=state.get("turn_id"),
                cost_governor=services.cost,
            )
            world_bible_payload = world_bible.model_dump()
            updates["world_bible"] = world_bible_payload

        _set_skill_if_available(activation, services, "campaign-seed-generation")
        if state.get("campaign_seed") is None:
            campaign_seed = generate_campaign_seed(
                world_bible=WorldBible.model_validate(world_bible_payload),
                player_profile=state["player_profile"],
                llm_client=cast(LLMClient, services.llm),
                turn_id=state.get("turn_id"),
                cost_governor=services.cost,
            )
            updates["campaign_seed"] = campaign_seed.model_dump()

    if state.get("memory_packet") is None:
        conn = getattr(services, "transcript_conn", None)
        vault_service = getattr(services, "vault_service", None)
        memory_packet = (
            assemble_memory_packet(state, conn=conn, vault_service=vault_service)
            if vault_service is not None
            else assemble_memory_packet_stub(state, conn=conn)
        )
        updates["memory_packet"] = memory_packet.model_dump()
    current_brief_payload = state.get("scene_brief")
    current_brief = (
        SceneBrief.model_validate(current_brief_payload)
        if current_brief_payload is not None
        else None
    )
    branch = analyze_player_choice(
        player_input=state.get("pending_player_input"),
        prior_scene_brief=current_brief,
        memory_packet=updates.get("memory_packet") or state.get("memory_packet"),
    )
    should_replan = _should_replan_scene(state, current_brief, branch.bypass_detected)
    if should_replan:
        if branch.bypass_detected:
            _set_skill_if_available(activation, services, "player-choice-branching")
            updates["oracle_bypass_detected"] = True
        if not _generated_campaign_context(updates):
            _set_skill_if_available(activation, services, "content-policy-routing")
        scene_intent = _scene_intent_from_state(
            state, current_brief, branch.revised_intent, state.get("content_policy")
        )
        route = safety_pre_gate(scene_intent, state.get("content_policy"))
        if isinstance(route, Blocked):
            _log_safety_event_to_service(
                services, state, "pre_gate_block", route.policy_ref, route.reason or "blocked"
            )
            return {
                **updates,
                "last_interrupt": _safety_block_interrupt(
                    state=state,
                    reason=route.reason or "blocked by content policy",
                ),
                "safety_events": [
                    *state.get("safety_events", []),
                    _safety_event(
                        state, route.policy_ref, "pre_gate_block", route.reason or "blocked"
                    ),
                ],
            }
        if isinstance(route, Rerouted):
            _log_safety_event_to_service(
                services, state, "pre_gate_reroute", route.policy_ref, route.reason or "rerouted"
            )
            updates["safety_events"] = [
                *state.get("safety_events", []),
                _safety_event(
                    state, route.policy_ref, "pre_gate_reroute", route.reason or "rerouted"
                ),
            ]

        if not _generated_campaign_context(updates):
            _set_skill_if_available(activation, services, "scene-brief-composition")
        try:
            updates["scene_brief"] = _compose_or_fallback_scene_brief(
                state=state,
                services=services,
                current_brief=current_brief,
                memory_packet=updates.get("memory_packet") or state.get("memory_packet"),
                scene_intent=route.intent,
                content_warnings=list(route.content_warnings),
            ).model_dump()
        except _BudgetStop as exc:
            return {
                **updates,
                "last_interrupt": _budget_stop_interrupt(state=state, reason=str(exc)),
            }
        updates["resolved_beat_ids"] = []
        updates["oracle_bypass_detected"] = False
    return updates


def _should_generate_campaign_context(state: dict[str, Any], services: AgentServices) -> bool:
    if state.get("phase") != "play":
        return False
    if services.llm is None:
        return False
    if state.get("world_bible") is not None and state.get("campaign_seed") is not None:
        return False
    return all(
        state.get(key) is not None for key in ("player_profile", "content_policy", "house_rules")
    )


def _generated_campaign_context(updates: dict[str, Any]) -> bool:
    return "world_bible" in updates or "campaign_seed" in updates


def _should_replan_scene(
    state: dict[str, Any],
    scene_brief: SceneBrief | None,
    branch_bypass_detected: bool,
) -> bool:
    if scene_brief is None:
        return True
    if branch_bypass_detected or bool(state.get("oracle_bypass_detected")):
        return True
    return bool(scene_brief.beat_ids) and set(state.get("resolved_beat_ids", [])) >= set(
        scene_brief.beat_ids
    )


def _scene_intent_from_state(
    state: dict[str, Any],
    current_brief: SceneBrief | None,
    revised_intent: str | None,
    content_policy: object | None = None,
) -> str:
    if revised_intent:
        return revised_intent
    player_input = (state.get("pending_player_input") or "").strip()
    if player_input:
        if _input_is_exact_policy_ref(player_input, content_policy):
            return player_input
        return f"Plan a scene that responds to player input: {player_input[:200]}"
    if current_brief is not None:
        return f"Continue campaign after completed scene: {current_brief.intent}"
    campaign_seed = state.get("campaign_seed") or {}
    selected_arc = campaign_seed.get("selected_arc", {}) if isinstance(campaign_seed, dict) else {}
    opening = selected_arc.get("opening_situation") if isinstance(selected_arc, dict) else None
    return str(opening or "Open the next first-slice scene.")


def _input_is_exact_policy_ref(player_input: str, content_policy: object | None) -> bool:
    if not isinstance(content_policy, dict):
        return False
    lowered = player_input.lower()
    terms = [*content_policy.get("hard_limits", []), *content_policy.get("soft_limits", {}).keys()]
    return any(
        lowered in {str(term).lower(), str(term).replace("_", " ").lower()} for term in terms
    )


def _compose_or_fallback_scene_brief(
    *,
    state: dict[str, Any],
    services: AgentServices,
    current_brief: SceneBrief | None,
    memory_packet: object,
    scene_intent: str,
    content_warnings: list[str],
) -> SceneBrief:
    if services.llm is None or state.get("content_policy") is None or memory_packet is None:
        return _fallback_scene_brief(scene_intent, content_warnings)
    return compose_scene_brief(
        player_input=state.get("pending_player_input"),
        memory_packet=memory_packet,
        content_policy=state["content_policy"],
        player_profile=state.get("player_profile"),
        world_bible=state.get("world_bible"),
        campaign_seed=state.get("campaign_seed"),
        prior_scene_brief=current_brief,
        scene_intent=scene_intent,
        llm_client=cast(LLMClient, services.llm),
        turn_id=state.get("turn_id"),
        cost_governor=services.cost,
    )


def _fallback_scene_brief(scene_intent: str, content_warnings: list[str]) -> SceneBrief:
    return SceneBrief(
        scene_id="scene_first_slice_001",
        intent=scene_intent,
        location=None,
        present_entities=[],
        beats=["Establish immediate stakes", "Offer a clear exploratory or social approach"],
        beat_ids=["beat_establish_stakes", "beat_offer_approach"],
        success_outs=["The next actionable lead becomes clear."],
        failure_outs=["The situation escalates without ending the scene."],
        pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        content_warnings=content_warnings,
    )


def _interrupt(
    *, kind: InterruptKind, state: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    return InterruptEnvelope.build(
        kind=kind,
        payload=payload,
        thread_id=f"campaign:{state.get('campaign_id', 'unknown')}",
    ).model_dump()


def _safety_block_interrupt(*, state: dict[str, Any], reason: str) -> dict[str, Any]:
    return _interrupt(kind=InterruptKind.SAFETY_BLOCK, state=state, payload={"reason": reason})


def _budget_stop_interrupt(*, state: dict[str, Any], reason: str) -> dict[str, Any]:
    return _interrupt(kind=InterruptKind.BUDGET_STOP, state=state, payload={"reason": reason})


def _safety_event(
    state: dict[str, Any], policy_ref: str | None, kind: str, action: str
) -> dict[str, Any]:
    return SafetyEvent(
        id=f"safety_{state.get('turn_id', 'turn')}_{kind}",
        turn_id=str(state.get("turn_id") or "unknown"),
        kind=kind,  # type: ignore[arg-type]
        policy_ref=policy_ref,
        action_taken=action[:200],
    ).model_dump()


def _set_skill_if_available(activation: Any, services: AgentServices, skill_name: str) -> None:
    if activation is None:
        return
    store = services.skill_store
    if store is not None and store.find(name=skill_name, agent_scope="oracle") is not None:
        activation.set_skill(skill_name)


def _log_safety_event_to_service(
    services: AgentServices,
    state: dict[str, Any],
    event_kind: str,
    policy_ref: str | None,
    reason: str,
) -> None:
    """Log a safety event via SafetyEventService (SQLite) when available."""
    safety_svc = services.safety
    if safety_svc is None:
        return
    campaign_id = state.get("campaign_id", "")
    turn_id = state.get("turn_id")
    try:
        if event_kind == "pre_gate_block":
            safety_svc.log_pre_gate_block(
                campaign_id=campaign_id,
                policy_ref=policy_ref or "",
                reason=reason,
                turn_id=turn_id,
            )
        elif event_kind == "pre_gate_reroute":
            safety_svc.log_pre_gate_reroute(
                campaign_id=campaign_id,
                policy_ref=policy_ref or "",
                reason=reason,
                turn_id=turn_id,
            )
    except Exception:
        # Roll back failed transaction so the connection stays usable
        with contextlib.suppress(Exception):
            safety_svc.conn.rollback()
