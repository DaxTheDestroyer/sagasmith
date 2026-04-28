"""Prompt contract for Oracle campaign-seed generation."""

from __future__ import annotations

import json

from sagasmith.schemas.campaign_seed import CampaignSeed
from sagasmith.schemas.player import PlayerProfile
from sagasmith.schemas.world import WorldBible

PROMPT_VERSION = "2026-04-28-1"

SYSTEM_PROMPT = f"""PROMPT_VERSION={PROMPT_VERSION}
You are SagaSmith's Oracle agent. Produce opening hooks and one selected first
arc from the hidden world bible. Return only JSON matching the provided schema.
Hooks must be distinct, playable, and aligned with the player profile.
""".strip()

JSON_SCHEMA: dict[str, object] = CampaignSeed.model_json_schema()


def build_user_prompt(world_bible: WorldBible, player_profile: PlayerProfile) -> str:
    """Render the user prompt for the structured campaign seed call."""

    payload = {
        "world_bible": world_bible.model_dump(mode="json"),
        "player_profile": player_profile.model_dump(mode="json"),
        "instructions": [
            "Create 3-5 distinct opening plot hooks.",
            "Select one hook as the initial arc and explain its opening situation.",
            "Keep mechanics requests descriptive only; deterministic services own dice, DCs, and damage.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
