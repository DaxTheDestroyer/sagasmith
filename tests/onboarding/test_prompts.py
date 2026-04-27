"""Tests for sagasmith.onboarding.prompts — phase catalog and parse_answer."""

from __future__ import annotations

import pytest

from sagasmith.onboarding.prompts import (
    ONBOARDING_PHASES,
    PHASE_ORDER,
    OnboardingPhase,
    PromptField,
    PromptFieldKind,
    parse_answer,
)

# ---------------------------------------------------------------------------
# Phase catalog
# ---------------------------------------------------------------------------


def test_ONBOARDING_PHASES_covers_all_phases() -> None:
    """ONBOARDING_PHASES must have exactly 9 entries in the correct phase order."""
    assert len(ONBOARDING_PHASES) == 9

    expected_phases = [
        OnboardingPhase.WELCOME,
        OnboardingPhase.TONE,
        OnboardingPhase.PILLARS,
        OnboardingPhase.COMBAT_DICE_UX,
        OnboardingPhase.CONTENT_POLICY,
        OnboardingPhase.LENGTH_DEATH,
        OnboardingPhase.BUDGET,
        OnboardingPhase.CHARACTER_MODE,
        OnboardingPhase.REVIEW,
    ]
    actual_phases = [p.phase for p in ONBOARDING_PHASES]
    assert actual_phases == expected_phases


def test_phase_order_includes_done() -> None:
    """PHASE_ORDER must end with DONE as the terminal state."""
    assert PHASE_ORDER[-1] == OnboardingPhase.DONE
    assert len(PHASE_ORDER) == 10  # 9 prompts + DONE


# ---------------------------------------------------------------------------
# PILLAR_BUDGET
# ---------------------------------------------------------------------------


def test_parse_answer_pillar_budget_normalizes() -> None:
    """Valid pillar budget normalizes integers to floats summing to 1.0."""
    fld = PromptField(
        id="pillar_budget",
        label="Pillars",
        kind=PromptFieldKind.PILLAR_BUDGET,
        choices=("combat", "exploration", "social", "puzzle"),
    )
    raw = {"combat": 3, "exploration": 3, "social": 3, "puzzle": 1}
    value, errors = parse_answer(fld, raw)

    assert errors == []
    assert isinstance(value, dict)
    assert value == {
        "combat": pytest.approx(0.3),
        "exploration": pytest.approx(0.3),
        "social": pytest.approx(0.3),
        "puzzle": pytest.approx(0.1),
    }
    assert abs(sum(value.values()) - 1.0) < 1e-9  # type: ignore[arg-type]


def test_parse_answer_pillar_budget_sum_not_ten() -> None:
    """A pillar budget that doesn't sum to 10 returns an error."""
    fld = PromptField(
        id="pillar_budget",
        label="Pillars",
        kind=PromptFieldKind.PILLAR_BUDGET,
        choices=("combat", "exploration", "social", "puzzle"),
    )
    raw = {"combat": 2, "exploration": 2, "social": 2, "puzzle": 2}  # sum = 8
    _, errors = parse_answer(fld, raw)

    assert errors
    assert "sum to 10" in errors[0]


def test_parse_answer_pillar_budget_negative_value() -> None:
    """A negative pillar value returns an error."""
    fld = PromptField(
        id="pillar_budget",
        label="Pillars",
        kind=PromptFieldKind.PILLAR_BUDGET,
    )
    raw = {"combat": -1, "exploration": 4, "social": 4, "puzzle": 3}
    _, errors = parse_answer(fld, raw)

    assert errors
    assert any(">= 0" in e for e in errors)


def test_parse_answer_pillar_budget_missing_key() -> None:
    """A pillar budget missing required keys returns an error."""
    fld = PromptField(
        id="pillar_budget",
        label="Pillars",
        kind=PromptFieldKind.PILLAR_BUDGET,
    )
    raw = {"combat": 4, "exploration": 3, "social": 3}  # missing puzzle
    _, errors = parse_answer(fld, raw)

    assert errors
    assert any("missing" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# SINGLE_CHOICE
# ---------------------------------------------------------------------------


def test_parse_answer_single_choice_accepts_valid() -> None:
    fld = PromptField(
        id="pacing",
        label="Pacing",
        kind=PromptFieldKind.SINGLE_CHOICE,
        choices=("slow", "medium", "fast"),
    )
    value, errors = parse_answer(fld, "medium")
    assert errors == []
    assert value == "medium"


def test_parse_answer_single_choice_rejects_unknown() -> None:
    """An invalid choice value returns an error mentioning valid choices."""
    fld = PromptField(
        id="pacing",
        label="Pacing",
        kind=PromptFieldKind.SINGLE_CHOICE,
        choices=("slow", "medium", "fast"),
    )
    _, errors = parse_answer(fld, "turbo")

    assert errors
    err = errors[0].lower()
    assert "slow" in err
    assert "medium" in err
    assert "fast" in err


# ---------------------------------------------------------------------------
# SOFT_LIMIT_MAP
# ---------------------------------------------------------------------------


def test_parse_answer_soft_limit_map_accepts_valid() -> None:
    fld = PromptField(
        id="soft_limits",
        label="Soft Limits",
        kind=PromptFieldKind.SOFT_LIMIT_MAP,
        required=False,
    )
    raw = {"violence": "fade_to_black", "language": "avoid_detail"}
    value, errors = parse_answer(fld, raw)
    assert errors == []
    assert value == raw


def test_parse_answer_soft_limit_map_rejects_bad_enum() -> None:
    """An invalid disposition value returns an error listing allowed values."""
    fld = PromptField(
        id="soft_limits",
        label="Soft Limits",
        kind=PromptFieldKind.SOFT_LIMIT_MAP,
        required=False,
    )
    _, errors = parse_answer(fld, {"violence": "redacted"})

    assert errors
    err = errors[0].lower()
    assert "fade_to_black" in err or "avoid_detail" in err or "ask_first" in err


def test_parse_answer_soft_limit_map_accepts_empty() -> None:
    """An empty soft_limits dict is valid (no defaults imposed)."""
    fld = PromptField(
        id="soft_limits",
        label="Soft Limits",
        kind=PromptFieldKind.SOFT_LIMIT_MAP,
        required=False,
    )
    value, errors = parse_answer(fld, {})
    assert errors == []
    assert value == {}


# ---------------------------------------------------------------------------
# FLOAT
# ---------------------------------------------------------------------------


def test_parse_answer_float_accepts_str() -> None:
    """A string float is converted to float."""
    fld = PromptField(id="per_session_usd", label="Budget", kind=PromptFieldKind.FLOAT)
    value, errors = parse_answer(fld, "2.50")
    assert errors == []
    assert value == pytest.approx(2.5)


def test_parse_answer_float_rejects_negative() -> None:
    fld = PromptField(id="per_session_usd", label="Budget", kind=PromptFieldKind.FLOAT)
    _, errors = parse_answer(fld, -1.0)
    assert errors


def test_parse_answer_float_accepts_zero() -> None:
    fld = PromptField(id="per_session_usd", label="Budget", kind=PromptFieldKind.FLOAT)
    value, errors = parse_answer(fld, 0)
    assert errors == []
    assert value == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# BOOL
# ---------------------------------------------------------------------------


def test_parse_answer_bool_accepts_y_n() -> None:
    """'y' → True; 'n' → False."""
    fld = PromptField(id="hard_stop", label="Hard Stop", kind=PromptFieldKind.BOOL)

    true_val, err = parse_answer(fld, "y")
    assert err == []
    assert true_val is True

    false_val, err = parse_answer(fld, "n")
    assert err == []
    assert false_val is False


def test_parse_answer_bool_accepts_native() -> None:
    fld = PromptField(id="hard_stop", label="Hard Stop", kind=PromptFieldKind.BOOL)
    v1, e1 = parse_answer(fld, True)
    v2, e2 = parse_answer(fld, False)
    assert e1 == [] and v1 is True
    assert e2 == [] and v2 is False


def test_parse_answer_bool_accepts_strings() -> None:
    fld = PromptField(id="flag", label="Flag", kind=PromptFieldKind.BOOL)
    for truthy in ("true", "yes", "True", "YES", "1"):
        v, e = parse_answer(fld, truthy)
        assert e == [], f"Expected no error for {truthy!r}"
        assert v is True
    for falsy in ("false", "no", "False", "NO", "0"):
        v, e = parse_answer(fld, falsy)
        assert e == [], f"Expected no error for {falsy!r}"
        assert v is False


def test_parse_answer_bool_rejects_invalid() -> None:
    fld = PromptField(id="flag", label="Flag", kind=PromptFieldKind.BOOL)
    _, errors = parse_answer(fld, "maybe")
    assert errors


# ---------------------------------------------------------------------------
# MULTI_TEXT
# ---------------------------------------------------------------------------


def test_parse_answer_multi_text_accepts_list() -> None:
    fld = PromptField(id="genre", label="Genre", kind=PromptFieldKind.MULTI_TEXT)
    value, errors = parse_answer(fld, ["high_fantasy", "dark_fantasy"])
    assert errors == []
    assert value == ["high_fantasy", "dark_fantasy"]


def test_parse_answer_multi_text_accepts_comma_string() -> None:
    fld = PromptField(id="genre", label="Genre", kind=PromptFieldKind.MULTI_TEXT)
    value, errors = parse_answer(fld, "high_fantasy, dark_fantasy")
    assert errors == []
    assert value == ["high_fantasy", "dark_fantasy"]


def test_parse_answer_multi_text_required_rejects_empty() -> None:
    fld = PromptField(id="genre", label="Genre", kind=PromptFieldKind.MULTI_TEXT, required=True)
    _, errors = parse_answer(fld, [])
    assert errors


def test_parse_answer_multi_text_optional_accepts_empty() -> None:
    fld = PromptField(
        id="preferences", label="Prefs", kind=PromptFieldKind.MULTI_TEXT, required=False
    )
    value, errors = parse_answer(fld, [])
    assert errors == []
    assert value == []
