"""Plain-text dice reveal rendering for deterministic Phase 5 checks."""

from __future__ import annotations

from sagasmith.schemas.mechanics import CheckResult


def _format_modifier(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def _format_dc(dc: int | None) -> str:
    return "—" if dc is None else str(dc)


def render_reveal_check(result: CheckResult, *, reason: str) -> str:
    """Render reveal-mode details for an already-resolved check result."""

    roll = result.roll_result
    # UI-SPEC §141 item 3: this reveals an already-recorded RollResult; display never rolls again.
    return "\n".join(
        [
            "Reveal Check",
            f"Reason: {reason}",
            "d20 + modifier vs DC",
            f"DC: {_format_dc(roll.dc)}",
            f"Modifier: {_format_modifier(roll.modifier)}",
            f"d20 result: {roll.natural}",
            f"Total: {roll.total}",
            f"Degree: {result.degree}",
            f"Saved to roll log: {roll.roll_id}",
        ]
    )


def render_compact_roll_line(result: CheckResult, *, reason: str) -> str:
    """Render the persisted compact roll transcript line."""

    roll = result.roll_result
    return (
        f"[roll] {reason}: d20 {roll.natural} + {roll.modifier} = {roll.total} "
        f"vs DC {_format_dc(roll.dc)} — {result.degree} ({roll.roll_id})"
    )
