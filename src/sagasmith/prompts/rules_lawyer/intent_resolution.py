"""Prompt contract for RulesLawyer intent resolution fallback."""

from __future__ import annotations

from typing import Any

PROMPT_VERSION = "2026-04-28-1"

SYSTEM_PROMPT = f"""RulesLawyer intent resolver prompt version {PROMPT_VERSION}.

Identify whether the player's text describes a first-slice PF2e mechanical action.
You may classify intent only. Do not invent modifiers, DCs, damage, action counts,
degrees of success, HP changes, or roll outcomes. Deterministic services will choose
all math and validate every proposal.
"""

JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skill_check", "start_combat", "strike", "move", "end_turn", "none"],
                    },
                    "stat": {"type": ["string", "null"]},
                    "target_id": {"type": ["string", "null"]},
                    "attack_id": {"type": ["string", "null"]},
                    "position": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reason": {"type": "string"},
                },
                "required": [
                    "action",
                    "stat",
                    "target_id",
                    "attack_id",
                    "position",
                    "confidence",
                    "reason",
                ],
            },
        }
    },
    "required": ["candidates"],
}


def build_user_prompt(player_input: str, scene_context: dict[str, Any] | None = None) -> str:
    """Render bounded context for first-slice intent classification."""

    context = scene_context or {}
    available_stats = ", ".join(_string_list(context.get("available_stats"))) or (
        "athletics, acrobatics, survival, intimidation, perception"
    )
    available_targets = ", ".join(_string_list(context.get("available_targets"))) or (
        "enemy_weak_melee, enemy_weak_ranged"
    )
    available_attacks = ", ".join(_string_list(context.get("available_attacks"))) or "longsword, shortbow"
    return "\n".join(
        [
            "Classify the player input into first-slice intent candidates.",
            f"Player input: {player_input!r}",
            f"Allowed stats: {available_stats}",
            f"Allowed targets: {available_targets}",
            f"Allowed attacks: {available_attacks}",
            "Allowed positions: close, near, far, behind_cover",
            "Return action='none' if no supported mechanical action is present.",
            "Never return math values; DCs/modifiers are deterministic-service owned.",
        ]
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
