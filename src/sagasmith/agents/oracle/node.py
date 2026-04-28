"""Oracle agent node.

Phase 6 replaces the stub with scene-brief-composition skill per
oracle-skills.md §2.3.
"""

from __future__ import annotations

from typing import Any, cast

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet_stub,
)
from sagasmith.agents.oracle.skills.campaign_seed_generation.logic import generate_campaign_seed
from sagasmith.agents.oracle.skills.world_bible_generation.logic import generate_world_bible
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.graph.bootstrap import AgentServices
from sagasmith.providers import LLMClient
from sagasmith.schemas.narrative import SceneBrief
from sagasmith.schemas.world import WorldBible

_FIRST_SLICE_STUB_SCENE_BRIEF = SceneBrief(
    scene_id="scene_stub_001",
    intent="placeholder first-slice scene (replaced in Phase 6)",
    location=None,
    present_entities=[],
    beats=[],
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
        memory_packet = assemble_memory_packet_stub(
            state,
            conn=getattr(services, "transcript_conn", None),
        )
        updates["memory_packet"] = memory_packet.model_dump()
    if state["scene_brief"] is None:
        if not _generated_campaign_context(updates):
            _set_skill_if_available(activation, services, "scene-brief-composition")
        updates["scene_brief"] = _FIRST_SLICE_STUB_SCENE_BRIEF.model_dump()
    return updates


def _should_generate_campaign_context(state: dict[str, Any], services: AgentServices) -> bool:
    if state.get("phase") != "play":
        return False
    if services.llm is None:
        return False
    if state.get("world_bible") is not None and state.get("campaign_seed") is not None:
        return False
    return all(
        state.get(key) is not None
        for key in ("player_profile", "content_policy", "house_rules")
    )


def _generated_campaign_context(updates: dict[str, Any]) -> bool:
    return "world_bible" in updates or "campaign_seed" in updates


def _set_skill_if_available(activation: Any, services: AgentServices, skill_name: str) -> None:
    if activation is None:
        return
    store = services.skill_store
    if store is not None and store.find(name=skill_name, agent_scope="oracle") is not None:
        activation.set_skill(skill_name)
