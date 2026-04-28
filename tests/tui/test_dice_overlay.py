"""Tests for Phase 5 reveal-mode dice detail rendering."""

from __future__ import annotations

from sagasmith.schemas.mechanics import CheckResult, RollResult
from sagasmith.tui.widgets.dice_overlay import render_compact_roll_line, render_reveal_check


def _check_result() -> CheckResult:
    return CheckResult(
        proposal_id="check_force_gate",
        roll_result=RollResult(
            roll_id="roll_abc123",
            seed="seed-1",
            die="d20",
            natural=14,
            modifier=7,
            total=21,
            dc=18,
            timestamp="2026-04-28T11:30:00Z",
        ),
        degree="success",
        effects=[],
        state_deltas=[],
    )


def test_render_reveal_check_includes_audit_details_without_modal_prompts() -> None:
    text = render_reveal_check(_check_result(), reason="force stuck gate")

    assert "Reveal Check" in text
    assert "d20 + modifier vs DC" in text
    assert "Reason: force stuck gate" in text
    assert "DC: 18" in text
    assert "Modifier: +7" in text
    assert "d20 result: 14" in text
    assert "Total: 21" in text
    assert "Degree: success" in text
    assert "Saved to roll log: roll_abc123" in text
    assert "Press Enter to reveal" not in text
    assert "Press Enter to roll" not in text
    assert "Esc: close details" not in text
    assert "Enter: continue" not in text


def test_render_compact_roll_line_uses_exact_transcript_pattern() -> None:
    line = render_compact_roll_line(_check_result(), reason="force stuck gate")

    assert line == "[roll] force stuck gate: d20 14 + 7 = 21 vs DC 18 — success (roll_abc123)"
