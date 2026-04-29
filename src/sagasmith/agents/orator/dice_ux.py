"""Dice UX mode handling for the Orator narration pipeline.

Modes (from PlayerProfile.dice_ux / HouseRules.dice_ux):
- auto:   Weave roll outcomes seamlessly into narration prose.
- reveal: Narrate the attempt, pause for dice overlay, resume with outcome.
- hidden: Never name rolls, DCs, modifiers, or mechanical terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sagasmith.schemas.mechanics import CheckResult

DiceUxMode = Literal["auto", "reveal", "hidden"]

# Mechanical terms that hidden mode strips from prompt instructions
_HIDDEN_TERMS = (
    "DC",
    "dc",
    "modifier",
    "natural",
    "total",
    "degree of success",
    "critical success",
    "critical failure",
    "d20",
    "roll",
    "rolled",
    "check",
)


@dataclass(frozen=True)
class DiceUxContext:
    """Prepared context for the Orator prompt based on dice UX mode.

    ``prompt_instruction`` is injected into the Orator system or user prompt
    to tell the LLM how to handle mechanical outcomes.
    ``constraint_payload`` is the structured mechanical data to include.
    """

    mode: DiceUxMode
    prompt_instruction: str
    constraint_payload: list[dict[str, object]]


def prepare_dice_ux(
    mode: DiceUxMode,
    check_results: list[CheckResult],
) -> DiceUxContext:
    """Build the dice-UX context for the Orator prompt.

    Returns instruction text and structured constraint data based on the
    configured dice UX mode.
    """
    constraints: list[dict[str, object]] = []
    for cr in check_results:
        entry: dict[str, object] = {
            "proposal_id": cr.proposal_id,
            "degree": cr.degree,
            "actor_id": cr.proposal_id.split("_")[-1] if "_" in cr.proposal_id else "player",
        }
        # Include damage/HP info from effects if present
        if cr.effects:
            for eff in cr.effects:
                entry.setdefault("effects", [])
                assert isinstance(entry["effects"], list)
                entry["effects"].append(
                    {
                        "kind": eff.kind,
                        "description": eff.description,
                        "target_id": eff.target_id,
                    }
                )
        constraints.append(entry)

    if mode == "auto":
        instruction = (
            "Weave the mechanical outcomes naturally into the narration. "
            "The reader should feel the dice results through the story prose "
            "without seeing raw numbers or mechanical terms. "
            "Describe successes and failures through vivid action language."
        )
    elif mode == "reveal":
        instruction = (
            "Narrate the attempt first, then clearly state the dice result "
            "and mechanical outcome. Include roll totals and degree of success. "
            "Format mechanical details on their own line for clarity. "
            "The player has chosen to see all dice details."
        )
    else:  # hidden
        instruction = (
            "Never mention dice, rolls, DCs, modifiers, totals, or mechanical "
            "terms. Describe only the narrative outcome. "
            "If a check was made, describe only what the character observes or "
            "experiences — not the numbers behind it."
        )

    return DiceUxContext(
        mode=mode,
        prompt_instruction=instruction,
        constraint_payload=constraints,
    )
