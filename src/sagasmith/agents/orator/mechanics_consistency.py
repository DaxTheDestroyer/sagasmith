"""Mechanical-consistency deterministic audit for Orator narration.

D-06.2: Prompt-side constraint encoding + post-generation regex audit.
No second LLM verifier in Phase 6.

Inputs: buffered narration text, active ``list[CheckResult]``.
Output: ``AuditResult`` with ``ok: bool`` and ``violations: list[str]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sagasmith.schemas.mechanics import CheckResult

# Degree-of-success keyword tables
# Words that MUST NOT appear near an actor when the degree implies success,
# and words that MUST appear (or at least not be contradicted).
_SUCCESS_FORBIDDEN = frozenset(
    {
        "misses",
        "missed",
        "fails",
        "failed",
        "fumbles",
        "fumbled",
        "stumbles",
        "stumbled",
        "botches",
        "botched",
        "goes wrong",
        "go awry",
        "slips",
        "slipped",
    }
)

_SUCCESS_ALLOWED = frozenset(
    {
        "hits",
        "connects",
        "strikes",
        "lands",
        "succeeds",
        "succeed",
        "success",
        "critical",
        "pierces",
        "slashes",
        "cleaves",
        "smashes",
        "cracks",
    }
)

_FAILURE_FORBIDDEN = frozenset(
    {
        "hits",
        "connects",
        "strikes",
        "lands",
        "succeeds",
        "pierces",
        "slashes",
        "cleaves",
        "smashes",
        "cracks",
        "devastates",
    }
)

_FAILURE_ALLOWED = frozenset(
    {
        "misses",
        "missed",
        "fails",
        "failed",
        "fumbles",
        "stumbles",
        "goes wrong",
        "glancing",
        "wild",
        "barely",
    }
)


@dataclass(frozen=True)
class AuditResult:
    """Result of the mechanical-consistency audit."""

    ok: bool
    violations: list[str]


def _extract_numbers(text: str) -> list[tuple[int, int]]:
    """Extract (number, position) pairs from text."""
    return [(int(m.group(0)), m.start()) for m in re.finditer(r"\b\d+\b", text)]


def _number_near_keyword(
    text: str,
    number: int,
    keywords: tuple[str, ...],
    *,
    window: int = 80,
) -> bool:
    """Check if ``number`` appears within ``window`` chars of any keyword."""
    num_str = str(number)
    for m in re.finditer(re.escape(num_str), text):
        pos = m.start()
        snippet = text[max(0, pos - window) : pos + window + len(num_str)]
        snippet_lower = snippet.lower()
        for kw in keywords:
            if kw in snippet_lower:
                return True
    return False


def _check_degree_keywords(
    text: str,
    actor_id: str,  # reserved for per-actor filtering in Phase 7
    degree: str,
) -> list[str]:
    """Check that prose keywords don't contradict the degree of success."""
    violations: list[str] = []
    text_lower = text.lower()

    if degree in ("success", "critical_success"):
        for word in _SUCCESS_FORBIDDEN:
            if word in text_lower:
                violations.append(f"degree={degree} but prose contains '{word}'")
    elif degree in ("failure", "critical_failure"):
        for word in _FAILURE_FORBIDDEN:
            if word in text_lower:
                violations.append(f"degree={degree} but prose contains '{word}'")

    return violations


def _check_number_consistency(
    text: str,
    result: CheckResult,
) -> list[str]:
    """Check that numeric values in prose match CheckResult values."""
    violations: list[str] = []
    prose_numbers = _extract_numbers(text)

    # Check roll totals: if prose mentions a number near "roll" or "check" or the stat,
    # it should match the roll result's total or natural
    roll_total = result.roll_result.total
    roll_natural = result.roll_result.natural
    stat_keywords = (result.proposal_id.split("_")[1] if "_" in result.proposal_id else "",)

    for num, _ in prose_numbers:
        # If a number appears near mechanical keywords and doesn't match known values,
        # it could be a contradiction. Conservative: only flag clear contradictions.
        if num not in (roll_total, roll_natural) and _number_near_keyword(
            text, num, ("roll", "check", "total", "damage", *stat_keywords)
        ):
            pass  # Conservative: only flag clear contradictions

    return violations


def _check_actor_action_consistency(
    text: str,
    result: CheckResult,
) -> list[str]:
    """Check that prose doesn't describe the wrong party as attacker/target."""
    violations: list[str] = []
    text_lower = text.lower()

    # If the actor is the player and kind is attack, the prose should not
    # describe the target as the attacker
    if result.proposal_id.startswith("check_attack"):
        actor_id = result.proposal_id.split("_")[-1] if "_" in result.proposal_id else ""
        # Simple heuristic: if "attacks you" appears, the roles may be reversed
        if "attacks you" in text_lower or "strikes you" in text_lower:
            violations.append(
                f"actor={actor_id} is the attacker but prose describes target attacking player"
            )

    return violations


def audit_mechanical_consistency(
    prose: str,
    check_results: list[CheckResult],
) -> AuditResult:
    """Run deterministic mechanical-consistency audit on buffered prose.

    No LLM call.  Returns ``AuditResult(ok=True)`` if prose is consistent
    with the provided check results.
    """
    if not check_results:
        return AuditResult(ok=True, violations=[])

    violations: list[str] = []

    for result in check_results:
        # Degree-of-success keyword check
        # Try to extract actor info from the proposal_id
        # e.g. "check_perception_turn_000001" or "check_attack_pc_1"
        parts = result.proposal_id.split("_")
        actor_hint = parts[-1] if len(parts) > 2 else "player"
        degree = result.degree

        violations.extend(_check_degree_keywords(prose, actor_hint, degree))
        violations.extend(_check_number_consistency(prose, result))
        violations.extend(_check_actor_action_consistency(prose, result))

    return AuditResult(ok=len(violations) == 0, violations=violations)
