"""Player choice branching skill logic for the Oracle agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.schemas.narrative import MemoryPacket, SceneBrief

BranchKind = Literal["continue", "bypass", "reject", "reframe"]


@dataclass(frozen=True)
class BranchingDecision:
    kind: BranchKind
    bypass_detected: bool
    revised_intent: str | None
    reason: str


_REJECTION_MARKERS = (
    "ignore",
    "refuse",
    "walk away",
    "leave",
    "instead",
    "avoid",
    "bypass",
    "skip",
    "don't",
    "do not",
    "not going",
)


def analyze_player_choice(
    *,
    player_input: str | None,
    prior_scene_brief: SceneBrief | dict[str, Any] | None,
    memory_packet: MemoryPacket | dict[str, Any] | None = None,
) -> BranchingDecision:
    """Detect whether player input bypasses, rejects, or reframes the active brief."""

    del memory_packet  # Reserved for future richer analysis; keep function pure now.
    text = (player_input or "").strip()
    if not text or prior_scene_brief is None:
        return BranchingDecision("continue", False, None, "no prior scene or input")

    brief = SceneBrief.model_validate(prior_scene_brief)
    lowered = text.lower()
    marker = next((candidate for candidate in _REJECTION_MARKERS if candidate in lowered), None)
    if marker is None:
        return BranchingDecision("continue", False, None, "input can continue active scene")

    if any(word in lowered for word in ("instead", "rather", "new plan")):
        kind: BranchKind = "reframe"
        revised = f"Reframe scene around player choice: {text[:160]}"
    elif marker in {"ignore", "bypass", "skip", "avoid"}:
        kind = "bypass"
        revised = f"Plan around bypass of scene {brief.scene_id}: {text[:160]}"
    else:
        kind = "reject"
        revised = f"Respect rejection of scene {brief.scene_id}: {text[:160]}"
    return BranchingDecision(kind, True, revised, f"matched player-choice marker: {marker}")
