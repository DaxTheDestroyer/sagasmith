"""Prompt contract for Oracle world-bible generation."""

from __future__ import annotations

import json

from sagasmith.schemas.player import ContentPolicy, HouseRules, PlayerProfile
from sagasmith.schemas.world import WorldBible

PROMPT_VERSION = "2026-04-28-1"

SYSTEM_PROMPT = f"""PROMPT_VERSION={PROMPT_VERSION}
You are SagaSmith's Oracle agent. Create hidden GM-only campaign world context.
Return only JSON matching the provided schema. Respect player hard limits, avoid
spoilers in player-facing wording, and keep PF2e rules deterministic-service owned.
""".strip()

JSON_SCHEMA: dict[str, object] = WorldBible.model_json_schema()


def build_user_prompt(
    player_profile: PlayerProfile,
    content_policy: ContentPolicy,
    house_rules: HouseRules,
) -> str:
    """Render the user prompt for the structured world bible call."""

    payload = {
        "player_profile": player_profile.model_dump(mode="json"),
        "content_policy": content_policy.model_dump(mode="json"),
        "house_rules": house_rules.model_dump(mode="json"),
        "instructions": [
            "Create a coherent hidden setting bible for a solo PF2e MVP campaign.",
            "Align theme, tone, locations, factions, NPCs, and conflicts with onboarding preferences.",
            "Do not include API keys, auth headers, or generated secret material.",
            "Include safety_notes explaining how hard limits are avoided.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
