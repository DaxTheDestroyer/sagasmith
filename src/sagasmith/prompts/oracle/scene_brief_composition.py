"""Prompt contract for Oracle scene-brief composition."""

from __future__ import annotations

import json
from typing import Any

from sagasmith.schemas.campaign_seed import CampaignSeed
from sagasmith.schemas.narrative import MemoryPacket, SceneBrief
from sagasmith.schemas.player import ContentPolicy, PlayerProfile
from sagasmith.schemas.world import WorldBible

PROMPT_VERSION = "2026-04-28-1"

SYSTEM_PROMPT = f"""PROMPT_VERSION={PROMPT_VERSION}
You are SagaSmith's Oracle agent. Produce hidden planning artifacts only.
Return only JSON matching the provided SceneBrief schema. Do not narrate to the
player, do not write second-person prose, and do not invent PF2e mechanics math.
Use readable beat text plus stable beat_ids so Orator can later report resolved
beat IDs. Respect hard limits and route around soft limits before generation.
""".strip()

JSON_SCHEMA: dict[str, object] = SceneBrief.model_json_schema()


def build_user_prompt(
    *,
    player_input: str | None,
    memory_packet: MemoryPacket,
    content_policy: ContentPolicy,
    player_profile: PlayerProfile | None,
    world_bible: WorldBible | None,
    campaign_seed: CampaignSeed | None,
    prior_scene_brief: SceneBrief | None,
    scene_intent: str,
) -> str:
    """Render the structured scene-brief request."""

    payload: dict[str, Any] = {
        "player_input": player_input,
        "scene_intent": scene_intent,
        "memory_packet": memory_packet.model_dump(mode="json"),
        "content_policy": content_policy.model_dump(mode="json"),
        "player_profile": player_profile.model_dump(mode="json") if player_profile else None,
        "world_bible": world_bible.model_dump(mode="json") if world_bible else None,
        "campaign_seed": campaign_seed.model_dump(mode="json") if campaign_seed else None,
        "prior_scene_brief": prior_scene_brief.model_dump(mode="json")
        if prior_scene_brief
        else None,
        "instructions": [
            "Compose a concise SceneBrief planning artifact for the next playable scene.",
            "Include beat_ids parallel to beats; IDs must be stable snake_case strings.",
            "Keep beats as audit-readable plan notes, not player-facing prose.",
            "Use success_outs/failure_outs as possible consequences, not guaranteed outcomes.",
            "List mechanical_triggers only as requests; deterministic rules own DCs and math.",
            "Never include API keys, auth headers, secrets, or GM-only spoiler prose for the player.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
