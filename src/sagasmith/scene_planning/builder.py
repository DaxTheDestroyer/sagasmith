"""Scene Planning: assemble the Oracle's scene plan for one play turn.

Consumes state and injected collaborators; produces a ScenePlan value.
Never constructs LangGraph interrupts or envelopes — that is the Adapter's
responsibility (ADR-0001 lines 113-116).
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
    assemble_memory_packet_stub,
)
from sagasmith.agents.oracle.skills.campaign_seed_generation.logic import generate_campaign_seed
from sagasmith.agents.oracle.skills.player_choice_branching.logic import analyze_player_choice
from sagasmith.agents.oracle.skills.scene_brief_composition.logic import compose_scene_brief
from sagasmith.agents.oracle.skills.world_bible_generation.logic import generate_world_bible
from sagasmith.providers import LLMClient
from sagasmith.safety_guard import IntentBlocked, IntentRerouted, SafetyGuard
from sagasmith.schemas.narrative import SceneBrief
from sagasmith.schemas.provider import ProviderConfig
from sagasmith.schemas.safety_cost import SafetyEvent
from sagasmith.schemas.world import WorldBible
from sagasmith.services.errors import BudgetStopError
from sagasmith.vault import VaultService


@dataclass(frozen=True)
class ScenePlanContext:
    """Everything plan_scene needs. Plain mapping and injected collaborators."""

    state: Mapping[str, Any]
    llm: LLMClient | None
    cost: Any
    safety: Any
    skill_store: Any
    transcript_conn: sqlite3.Connection | None
    vault_service: VaultService | None
    provider_config: ProviderConfig | None


@dataclass(frozen=True)
class InterruptIntent:
    """A pending interrupt, to be wrapped into an InterruptEnvelope by the Adapter."""

    kind: Literal["safety_block", "budget_stop"]
    reason: str


@dataclass(frozen=True)
class ScenePlan:
    """Result of plan_scene: everything the Adapter needs to project onto state."""

    state_updates: Mapping[str, Any]
    interrupt: InterruptIntent | None
    pre_gate_events: tuple[SafetyEvent, ...]
    skills_activated: tuple[str, ...]


def plan_scene(context: ScenePlanContext) -> ScenePlan:
    """Produce the Oracle's scene plan from state and collaborators.

    Coordinates campaign-context generation, memory packet assembly,
    player-choice branching, safety pre-gate, and scene-brief composition
    into a single explicit ScenePlan value.
    """
    state = context.state
    updates: dict[str, Any] = {}
    skills_activated: list[str] = []
    pre_gate_events: list[SafetyEvent] = []

    if _should_generate_campaign_context(state, context):
        if _skill_registered(context.skill_store, "world-bible-generation"):
            skills_activated.append("world-bible-generation")
        world_bible_payload = state.get("world_bible")
        if world_bible_payload is None:
            world_bible = generate_world_bible(
                player_profile=state["player_profile"],
                content_policy=state["content_policy"],
                house_rules=state["house_rules"],
                llm_client=cast(LLMClient, context.llm),
                model=_default_model(context),
                cheap_model=_cheap_model(context),
                turn_id=state.get("turn_id"),
                cost_governor=context.cost,
            )
            world_bible_payload = world_bible.model_dump()
            updates["world_bible"] = world_bible_payload

        if _skill_registered(context.skill_store, "campaign-seed-generation"):
            skills_activated.append("campaign-seed-generation")
        if state.get("campaign_seed") is None:
            campaign_seed = generate_campaign_seed(
                world_bible=WorldBible.model_validate(world_bible_payload),
                player_profile=state["player_profile"],
                llm_client=cast(LLMClient, context.llm),
                model=_default_model(context),
                cheap_model=_cheap_model(context),
                turn_id=state.get("turn_id"),
                cost_governor=context.cost,
            )
            updates["campaign_seed"] = campaign_seed.model_dump()

    if state.get("memory_packet") is None:
        memory_packet = (
            assemble_memory_packet(
                state, conn=context.transcript_conn, vault_service=context.vault_service
            )
            if context.vault_service is not None
            else assemble_memory_packet_stub(state, conn=context.transcript_conn)
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
            if _skill_registered(context.skill_store, "player-choice-branching"):
                skills_activated.append("player-choice-branching")
            updates["oracle_bypass_detected"] = True
        if not _generated_campaign_context(updates) and _skill_registered(
            context.skill_store, "content-policy-routing"
        ):
            skills_activated.append("content-policy-routing")
        scene_intent = _scene_intent_from_state(
            state, current_brief, branch.revised_intent, state.get("content_policy")
        )
        safety_guard = SafetyGuard(state.get("content_policy"))
        route = safety_guard.route_intent(scene_intent)
        if isinstance(route, IntentBlocked):
            _log_safety_event_to_service(
                context.safety, state, "pre_gate_block", route.policy_ref, route.reason or "blocked"
            )
            block_event = _build_safety_event(
                safety_guard, state, route.policy_ref, "pre_gate_block", route.reason or "blocked"
            )
            return ScenePlan(
                state_updates=updates,
                interrupt=InterruptIntent(
                    kind="safety_block",
                    reason=route.reason or "blocked by content policy",
                ),
                pre_gate_events=(block_event,),
                skills_activated=tuple(skills_activated),
            )
        if isinstance(route, IntentRerouted):
            _log_safety_event_to_service(
                context.safety,
                state,
                "pre_gate_reroute",
                route.policy_ref,
                route.reason or "rerouted",
            )
            pre_gate_events.append(
                _build_safety_event(
                    safety_guard,
                    state,
                    route.policy_ref,
                    "pre_gate_reroute",
                    route.reason or "rerouted",
                )
            )

        if not _generated_campaign_context(updates) and _skill_registered(
            context.skill_store, "scene-brief-composition"
        ):
            skills_activated.append("scene-brief-composition")
        try:
            updates["scene_brief"] = _compose_or_fallback_scene_brief(
                state=state,
                context=context,
                current_brief=current_brief,
                memory_packet=updates.get("memory_packet") or state.get("memory_packet"),
                scene_intent=route.intent,
                content_warnings=list(route.content_warnings),
            ).model_dump()
        except BudgetStopError as exc:
            return ScenePlan(
                state_updates=updates,
                interrupt=InterruptIntent(kind="budget_stop", reason=str(exc)),
                pre_gate_events=tuple(pre_gate_events),
                skills_activated=tuple(skills_activated),
            )
        updates["resolved_beat_ids"] = []
        updates["oracle_bypass_detected"] = False

    return ScenePlan(
        state_updates=updates,
        interrupt=None,
        pre_gate_events=tuple(pre_gate_events),
        skills_activated=tuple(skills_activated),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _should_generate_campaign_context(state: Mapping[str, Any], context: ScenePlanContext) -> bool:
    if state.get("phase") != "play":
        return False
    if context.llm is None:
        return False
    if state.get("world_bible") is not None and state.get("campaign_seed") is not None:
        return False
    return all(
        state.get(key) is not None for key in ("player_profile", "content_policy", "house_rules")
    )


def _generated_campaign_context(updates: dict[str, Any]) -> bool:
    return "world_bible" in updates or "campaign_seed" in updates


def _should_replan_scene(
    state: Mapping[str, Any],
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
    state: Mapping[str, Any],
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
    state: Mapping[str, Any],
    context: ScenePlanContext,
    current_brief: SceneBrief | None,
    memory_packet: object,
    scene_intent: str,
    content_warnings: list[str],
) -> SceneBrief:
    if context.llm is None or state.get("content_policy") is None or memory_packet is None:
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
        llm_client=context.llm,
        model=_default_model(context),
        cheap_model=_cheap_model(context),
        turn_id=state.get("turn_id"),
        cost_governor=context.cost,
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


def _build_safety_event(
    safety_guard: SafetyGuard,
    state: Mapping[str, Any],
    policy_ref: str | None,
    kind: str,
    action: str,
) -> SafetyEvent:
    return safety_guard.make_event(
        str(state.get("turn_id") or "unknown"),
        kind,
        policy_ref,
        action,
        source="pre_gate",
    )


def _log_safety_event_to_service(
    safety_svc: Any,
    state: Mapping[str, Any],
    event_kind: str,
    policy_ref: str | None,
    reason: str,
) -> None:
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
        with contextlib.suppress(Exception):
            safety_svc.conn.rollback()


def _skill_registered(skill_store: Any, skill_name: str) -> bool:
    if skill_store is None:
        return False
    return skill_store.find(name=skill_name, agent_scope="oracle") is not None


def _default_model(context: ScenePlanContext) -> str:
    return (
        context.provider_config.default_model
        if context.provider_config is not None
        else "fake-default"
    )


def _cheap_model(context: ScenePlanContext) -> str:
    return (
        context.provider_config.cheap_model if context.provider_config is not None else "fake-cheap"
    )
