"""Shared test fixtures for the onboarding test suite.

``make_happy_path_answers()`` returns a list of 9 answer dicts — one per
onboarding phase in PHASE_ORDER — representing a known-good run.

Example values are loosely based on GAME_SPEC §12.4 ("Sample Onboarding Run").
"""

from __future__ import annotations


def make_happy_path_answers() -> list[dict[str, object]]:
    """Return a complete list of valid answers for all 9 onboarding phases.

    Phase order:
      0  WELCOME       → genre
      1  TONE          → tone, touchstones
      2  PILLARS       → pillar_budget, pacing
      3  COMBAT_DICE_UX → combat_style, dice_ux
      4  CONTENT_POLICY → hard_limits, soft_limits, preferences
      5  LENGTH_DEATH  → campaign_length, death_policy
      6  BUDGET        → per_session_usd, hard_stop
      7  CHARACTER_MODE → character_mode
      8  REVIEW        → review_confirmed
    """
    return [
        # 0 — WELCOME
        {
            "genre": ["high_fantasy", "dark_fantasy"],
        },
        # 1 — TONE
        {
            "tone": ["grim", "hopeful", "heroic"],
            "touchstones": ["Pathfinder Core Rulebook", "The Witcher", "Dragon Age Origins"],
        },
        # 2 — PILLARS
        {
            "pillar_budget": {
                "combat": 3,
                "exploration": 3,
                "social": 3,
                "puzzle": 1,
            },
            "pacing": "medium",
        },
        # 3 — COMBAT_DICE_UX
        {
            "combat_style": "theater_of_mind",
            "dice_ux": "reveal",
        },
        # 4 — CONTENT_POLICY
        {
            "hard_limits": ["sexual_content"],
            "soft_limits": {"graphic_violence": "fade_to_black"},
            "preferences": ["heroic_sacrifice", "moral_ambiguity"],
        },
        # 5 — LENGTH_DEATH
        {
            "campaign_length": "arc",
            "death_policy": "heroic_recovery",
        },
        # 6 — BUDGET
        {
            "per_session_usd": 2.50,
            "hard_stop": True,
        },
        # 7 — CHARACTER_MODE
        {
            "character_mode": "pregenerated",
        },
        # 8 — REVIEW
        {
            "review_confirmed": True,
        },
    ]
