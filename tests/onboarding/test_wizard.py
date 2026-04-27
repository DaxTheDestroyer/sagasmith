"""Tests for sagasmith.onboarding.wizard — OnboardingWizard state machine."""

from __future__ import annotations

from typing import Any, cast

import pytest

from sagasmith.onboarding.prompts import OnboardingPhase
from sagasmith.onboarding.wizard import OnboardingWizard

from .fixtures import make_happy_path_answers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_to_review(wizard: OnboardingWizard) -> None:
    """Drive the wizard through all phases up to (but not including) REVIEW confirmation."""
    answers = make_happy_path_answers()
    # Steps 0-7 (indices 0-7), skip the review_confirmed step (index 8)
    for i, answer_dict in enumerate(answers[:-1]):
        result = wizard.step(answer_dict)
        assert result.errors == [], f"Unexpected error at step {i}: {result.errors}"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_wizard_happy_path_reaches_done() -> None:
    """Driving all 9 steps with valid answers reaches DONE and sets is_complete."""
    wizard = OnboardingWizard()
    answers = make_happy_path_answers()

    for i, answer_dict in enumerate(answers):
        result = wizard.step(answer_dict)
        assert result.errors == [], f"Unexpected errors at step {i}: {result.errors}"

    assert result.phase == OnboardingPhase.DONE  # type: ignore[possibly-undefined]
    assert wizard.is_complete is True
    assert result.next_prompt is None  # type: ignore[possibly-undefined]


def test_wizard_starts_at_welcome() -> None:
    wizard = OnboardingWizard()
    assert wizard.current_prompt().phase == OnboardingPhase.WELCOME


def test_wizard_is_complete_false_at_start() -> None:
    wizard = OnboardingWizard()
    assert wizard.is_complete is False


# ---------------------------------------------------------------------------
# Error / non-advancing behaviour
# ---------------------------------------------------------------------------


def test_wizard_returns_error_without_advancing_on_bad_input() -> None:
    """An empty required MULTI_TEXT keeps the wizard on WELCOME with errors."""
    wizard = OnboardingWizard()
    result = wizard.step({"genre": []})

    assert result.errors, "Expected validation errors"
    assert result.phase == OnboardingPhase.WELCOME
    assert wizard.is_complete is False


def test_wizard_still_on_same_phase_after_bad_input() -> None:
    """current_prompt() stays on WELCOME after a failed step()."""
    wizard = OnboardingWizard()
    wizard.step({"genre": []})
    assert wizard.current_prompt().phase == OnboardingPhase.WELCOME


# ---------------------------------------------------------------------------
# build_records
# ---------------------------------------------------------------------------


def test_wizard_build_records_yields_valid_triple() -> None:
    """After happy path, build_records returns valid Pydantic triple."""
    from sagasmith.schemas.player import ContentPolicy, HouseRules, PlayerProfile

    wizard = OnboardingWizard()
    _run_to_review(wizard)

    profile, content_policy, house_rules = wizard.build_records()

    assert isinstance(profile, PlayerProfile)
    assert isinstance(content_policy, ContentPolicy)
    assert isinstance(house_rules, HouseRules)

    # Pillar weights: {combat:3, exploration:3, social:3, puzzle:1} → normalize
    import pytest as _pytest
    assert profile.pillar_weights == {
        "combat": _pytest.approx(0.3),
        "exploration": _pytest.approx(0.3),
        "social": _pytest.approx(0.3),
        "puzzle": _pytest.approx(0.1),
    }


def test_wizard_build_records_before_all_phases_raises() -> None:
    """build_records() raises RuntimeError if not all phases have been filled."""
    wizard = OnboardingWizard()
    with pytest.raises(RuntimeError, match="review called before all phases filled"):
        wizard.build_records()


def test_wizard_build_records_house_rules_defaults() -> None:
    """HouseRules from build_records has expected MVP defaults."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    _, _, house_rules = wizard.build_records()

    assert house_rules.initiative_visible is True
    assert house_rules.allow_retcon is True
    assert house_rules.auto_save_every_turn is True
    assert house_rules.session_end_trigger == "player_command_or_budget"


# ---------------------------------------------------------------------------
# Review step
# ---------------------------------------------------------------------------


def test_wizard_review_step_without_confirmation_stays_on_review() -> None:
    """review_confirmed=False keeps the wizard on REVIEW with an error."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    result = wizard.step({"review_confirmed": False})

    assert result.phase == OnboardingPhase.REVIEW
    assert result.errors
    assert "review not confirmed" in result.errors[0]


def test_wizard_review_step_with_confirmation_advances_to_done() -> None:
    """review_confirmed=True advances to DONE."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    result = wizard.step({"review_confirmed": True})

    assert result.phase == OnboardingPhase.DONE
    assert result.errors == []
    assert wizard.is_complete is True


# ---------------------------------------------------------------------------
# edit()
# ---------------------------------------------------------------------------


def test_wizard_edit_valid_field_updates_draft() -> None:
    """Editing a valid profile field updates the draft and is reflected in review()."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    errors = wizard.edit("profile.pacing", "fast")

    assert errors == []
    review = cast(dict[str, Any], wizard.review())
    assert review["profile"]["pacing"] == "fast"


def test_wizard_edit_invalid_field_reports_error() -> None:
    """Editing with an invalid value returns a non-empty error list; draft is unchanged."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    review_before = cast(dict[str, Any], wizard.review())
    errors = wizard.edit("profile.pacing", "turbo")

    assert errors, "Expected validation errors for 'turbo'"
    # Draft should be unchanged
    review_after = cast(dict[str, Any], wizard.review())
    assert review_after["profile"]["pacing"] == review_before["profile"]["pacing"]


def test_wizard_edit_combat_style_is_forbidden() -> None:
    """Editing combat_style via edit() returns the fixed-field error."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    errors = wizard.edit("profile.combat_style", "grid")

    assert errors == ["combat_style is fixed to 'theater_of_mind' in MVP"]


def test_wizard_edit_budget_sub_field() -> None:
    """Editing profile.budget.per_session_usd works correctly."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    errors = wizard.edit("profile.budget.per_session_usd", 5.0)
    assert errors == []
    review = cast(dict[str, Any], wizard.review())
    assert review["profile"]["budget"]["per_session_usd"] == pytest.approx(5.0)


def test_wizard_edit_dice_ux() -> None:
    """Editing house_rules.dice_ux works."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    errors = wizard.edit("house_rules.dice_ux", "hidden")
    assert errors == []
    review = cast(dict[str, Any], wizard.review())
    assert review["house_rules"]["dice_ux"] == "hidden"


def test_wizard_edit_content_policy_hard_limits() -> None:
    """Editing content_policy.hard_limits works."""
    wizard = OnboardingWizard()
    _run_to_review(wizard)

    errors = wizard.edit("content_policy.hard_limits", ["gore", "torture"])
    assert errors == []
    review = cast(dict[str, Any], wizard.review())
    assert "gore" in review["content_policy"]["hard_limits"]


# ---------------------------------------------------------------------------
# Completed wizard raises on current_prompt/step
# ---------------------------------------------------------------------------


def test_wizard_done_raises_on_current_prompt() -> None:
    wizard = OnboardingWizard()
    for answer_dict in make_happy_path_answers():
        wizard.step(answer_dict)

    with pytest.raises(RuntimeError, match="wizard complete"):
        wizard.current_prompt()


def test_wizard_done_raises_on_step() -> None:
    wizard = OnboardingWizard()
    for answer_dict in make_happy_path_answers():
        wizard.step(answer_dict)

    with pytest.raises(RuntimeError, match="wizard complete"):
        wizard.step({"review_confirmed": True})
