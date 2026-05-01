"""Orator agent node.

Plan 06-04: Buffered stream-after-classify pipeline replaces stub narration.
Tokens are accumulated in a private buffer, run through inline hard-limit
matcher + SafetyPostGate + mechanical-consistency audit BEFORE any tokens
reach pending_narration.  Player sees a paced playback of validated tokens.

Plan 06-07: SafetyPostGate integration for post-generation content scanning.
Two-rewrite limit enforced by this pipeline (not the post-gate service).
"""

from __future__ import annotations

from typing import Any

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
)
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.mechanics import CheckResult
from sagasmith.schemas.narrative import MemoryPacket, SceneBrief
from sagasmith.schemas.player import ContentPolicy, PlayerProfile
from sagasmith.schemas.safety_cost import SafetyEvent
from sagasmith.services.errors import BudgetStopError

_FALLBACK_NARRATION = "The scene shifts. A new detail draws your attention."


def orator_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Render scene narration through the buffered stream-after-classify pipeline.

    D-06.1: Tokens are buffered, validated, then played back.
    D-06.4: Emits resolved_beat_ids.
    D-06.6: Per-turn budget covers initial generation + up to two rewrites.
    On budget exhaustion, emits fallback narration and posts BUDGET_STOP.
    """
    if services._call_recorder is not None:
        services._call_recorder.append("orator")

    updates: dict[str, Any] = {}

    # Ensure memory context
    if state.get("memory_packet") is None:
        vault_service = getattr(services, "vault_service", None)
        memory_packet = assemble_memory_packet(
            state,
            conn=getattr(services, "transcript_conn", None),
            vault_service=vault_service,
        )
        updates["memory_packet"] = memory_packet.model_dump()

    activation = get_current_activation()
    if activation is not None:
        activation.set_skill("scene-rendering")

    if state.get("scene_brief") is None:
        return updates

    # --- Budget preflight (D-06.6) ---
    cost_governor = getattr(services, "cost", None)
    if cost_governor is not None:
        try:
            cost_governor.preflight(
                provider=_get_provider(state, services),
                model=_get_narration_model(state, services),
                prompt_tokens=256,  # conservative estimate
                max_tokens_fallback=1024,
            ).raise_if_blocked()
        except BudgetStopError:
            updates["pending_narration"] = state["pending_narration"] + [_FALLBACK_NARRATION]
            updates.setdefault("safety_events", [])
            updates["safety_events"] = [
                *state.get("safety_events", []),
                SafetyEvent(
                    id=f"safety_{state.get('turn_id', 'unknown')}_budget_stop",
                    turn_id=str(state.get("turn_id", "unknown")),
                    kind="fallback",
                    policy_ref=None,
                    action_taken="budget_exhausted:fallback_narration",
                ).model_dump(),
            ]
            return updates

    # --- Buffered stream-after-classify pipeline (D-06.1) ---
    scene_brief = _build_scene_brief(state["scene_brief"])
    check_results = _build_check_results(state.get("check_results", []))
    memory_packet = _build_memory_packet(state.get("memory_packet"))
    content_policy = _build_content_policy(state.get("content_policy"))
    player_profile = _build_player_profile(state.get("player_profile"))
    dice_ux_mode = _get_dice_ux_mode(state)

    llm_client = getattr(services, "llm", None)
    narration_model = _get_narration_model(state, services)
    cheap_model = _get_cheap_model(state, services)
    turn_id = str(state.get("turn_id", "unknown"))
    campaign_id = str(state.get("campaign_id", ""))
    safety_svc = getattr(services, "safety", None)

    from sagasmith.agents.orator.skills.scene_rendering.logic import render_scene

    result = render_scene(
        scene_brief=scene_brief,
        check_results=check_results,
        memory_packet=memory_packet,
        content_policy=content_policy,
        player_profile=player_profile,
        house_rules_dice_ux=dice_ux_mode,
        llm_client=llm_client,
        narration_model=narration_model,
        cheap_model=cheap_model,
        cost_governor=cost_governor,
        provider=_get_provider(state, services),
        turn_id=turn_id,
        campaign_id=campaign_id,
        safety_svc=safety_svc,
    )

    updates["pending_narration"] = state["pending_narration"] + result.narration_lines
    if result.resolved_beat_ids:
        existing = list(state.get("resolved_beat_ids", []))
        merged = list(dict.fromkeys(existing + result.resolved_beat_ids))
        updates["resolved_beat_ids"] = merged
    if result.safety_events:
        updates["safety_events"] = [*state.get("safety_events", []), *result.safety_events]

    return updates


# ---------------------------------------------------------------------------
# Helpers: extract typed objects from state dicts
# ---------------------------------------------------------------------------


def _get_provider(state: dict[str, Any], services: Any | None = None) -> str:
    provider_config = state.get("provider_config") or getattr(services, "provider_config", None)
    if provider_config is not None:
        if isinstance(provider_config, dict):
            return provider_config.get("provider", "fake")
        return getattr(provider_config, "provider", "fake")
    return "fake"


def _get_narration_model(state: dict[str, Any], services: Any | None = None) -> str:
    provider_config = state.get("provider_config") or getattr(services, "provider_config", None)
    if provider_config is not None:
        if isinstance(provider_config, dict):
            return provider_config.get("narration_model", "fake-narration")
        return getattr(provider_config, "narration_model", "fake-narration")
    return "fake-narration"


def _get_cheap_model(state: dict[str, Any], services: Any | None = None) -> str:
    provider_config = state.get("provider_config") or getattr(services, "provider_config", None)
    if provider_config is not None:
        if isinstance(provider_config, dict):
            return provider_config.get("cheap_model", "fake-cheap")
        return getattr(provider_config, "cheap_model", "fake-cheap")
    return "fake-cheap"


def _get_dice_ux_mode(state: dict[str, Any]) -> str | None:
    """Extract dice_ux from house_rules or player_profile."""
    hr = state.get("house_rules")
    if hr is not None:
        if isinstance(hr, dict):
            return hr.get("dice_ux")
        return getattr(hr, "dice_ux", None)
    pp = state.get("player_profile")
    if pp is not None:
        if isinstance(pp, dict):
            return pp.get("dice_ux")
        return getattr(pp, "dice_ux", None)
    return None


def _build_scene_brief(data: Any) -> SceneBrief | None:
    if data is None:
        return None
    if isinstance(data, SceneBrief):
        return data
    return SceneBrief.model_validate(data)


def _build_check_results(data: Any) -> list[CheckResult]:
    if not data:
        return []
    if data and isinstance(data[0], CheckResult):
        return data  # type: ignore[return-value]
    return [CheckResult.model_validate(cr) for cr in data]


def _build_memory_packet(data: Any) -> MemoryPacket:
    if data is None:
        return MemoryPacket(
            token_cap=256,
            summary="No prior context.",
            entities=[],
            recent_turns=[],
            open_callbacks=[],
            retrieval_notes=[],
        )
    if isinstance(data, MemoryPacket):
        return data
    return MemoryPacket.model_validate(data)


def _build_content_policy(data: Any) -> ContentPolicy | None:
    if data is None:
        return None
    if isinstance(data, ContentPolicy):
        return data
    return ContentPolicy.model_validate(data)


def _build_player_profile(data: Any) -> PlayerProfile | None:
    if data is None:
        return None
    if isinstance(data, PlayerProfile):
        return data
    return PlayerProfile.model_validate(data)
