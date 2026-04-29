"""Prompt contract for Orator scene rendering (D-06.5).

Encodes CheckResult payloads as structured constraint tokens and
provides the system/user prompt for LLM streaming narration.
"""

from __future__ import annotations

import json
from typing import Any

from sagasmith.schemas.mechanics import CheckResult
from sagasmith.schemas.narrative import MemoryPacket, SceneBrief
from sagasmith.schemas.player import ContentPolicy, PlayerProfile

PROMPT_VERSION = "2026-04-28-1"

SYSTEM_PROMPT = f"""PROMPT_VERSION={PROMPT_VERSION}
You are SagaSmith's Orator — the only player-facing narrative voice.
Render the scene described in the planning brief into vivid, engaging prose.

RULES:
- You are the sole narrator. Never break character or reference the system.
- Never contradict the mechanical outcomes provided as constraint tokens.
- Respect the dice UX mode instruction for how to present roll results.
- Respect the content policy — do not include hard-limit or soft-limit content.
- Use second-person ("you") for the player character.
- Keep narration concise (2-4 paragraphs) unless the scene demands more.
- Include location, NPCs, and sensory details from the brief.
- Advance at least one beat from the scene brief.
""".strip()


def build_user_prompt(
    *,
    scene_brief: SceneBrief,
    check_results: list[CheckResult],
    memory_packet: MemoryPacket,
    content_policy: ContentPolicy | None,
    player_profile: PlayerProfile | None,
    dice_ux_instruction: str,
    dice_ux_constraints: list[dict[str, object]],
    beat_ids: list[str],
) -> str:
    """Render the structured scene-rendering request.

    CheckResult payloads are encoded as structured constraint tokens with
    an explicit instruction not to contradict them (D-06.2 prompt-side
    constraint encoding).
    """
    payload: dict[str, Any] = {
        "scene_brief": {
            "scene_id": scene_brief.scene_id,
            "intent": scene_brief.intent,
            "location": scene_brief.location,
            "present_entities": scene_brief.present_entities,
            "beats": scene_brief.beats,
            "beat_ids": scene_brief.beat_ids,
            "success_outs": scene_brief.success_outs,
            "failure_outs": scene_brief.failure_outs,
            "pacing_target": scene_brief.pacing_target.model_dump(mode="json"),
        },
        "mechanical_constraints": dice_ux_constraints,
        "dice_ux_instruction": dice_ux_instruction,
        "memory_context": {
            "summary": memory_packet.summary,
            "recent_turns": memory_packet.recent_turns[-3:],  # last 3 turns
            "entities": [e.model_dump(mode="json") for e in memory_packet.entities[:5]],
            "open_callbacks": memory_packet.open_callbacks[:3],
        },
        "content_policy": (content_policy.model_dump(mode="json") if content_policy else None),
        "instructions": [
            "Render this scene as player-facing narration.",
            "DO NOT contradict any mechanical constraint tokens.",
            f"Dice UX mode instruction: {dice_ux_instruction}",
            "Identify which beat_ids your narration advances by including them in your response.",
            "Never include API keys, secrets, or GM-only spoiler content.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
