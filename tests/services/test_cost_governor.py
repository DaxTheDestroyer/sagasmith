"""Tests for CostGovernor and BudgetStopResult."""

from __future__ import annotations

import pytest

from sagasmith.schemas.provider import TokenUsage
from sagasmith.services.cost import BudgetStopResult, CostGovernor
from sagasmith.services.errors import BudgetStopError


def test_record_uses_provider_cost_when_present() -> None:
    gov = CostGovernor(1.0)
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        provider_cost_usd=0.05,
    )
    update = gov.record_usage(provider="fake", model="fake-default", usage=usage)
    assert update.cost_usd == 0.05
    assert update.cost_is_approximate is False


def test_record_falls_back_to_static_table() -> None:
    gov = CostGovernor(1.0)
    usage = TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )
    update = gov.record_usage(provider="fake", model="fake-default", usage=usage)
    assert update.cost_is_approximate is True
    assert update.cost_usd == pytest.approx(0.002)


def test_record_unknown_model_returns_zero_approximate() -> None:
    gov = CostGovernor(1.0)
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    update = gov.record_usage(provider="unknown", model="unknown", usage=usage)
    assert update.cost_usd == 0.0
    assert update.cost_is_approximate is True


@pytest.mark.smoke
def test_warning_70_fires_exactly_once() -> None:
    gov = CostGovernor(1.0)
    # spend $0.75
    usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.75)
    update1 = gov.record_usage(provider="fake", model="fake-default", usage=usage)
    assert update1.warnings_fired_this_call == ["70"]

    # spend another $0.10
    usage2 = TokenUsage(
        prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.10
    )
    update2 = gov.record_usage(provider="fake", model="fake-default", usage=usage2)
    assert update2.warnings_fired_this_call == []


@pytest.mark.smoke
def test_warning_90_fires_once_and_not_70_again() -> None:
    gov = CostGovernor(1.0)
    usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.75)
    gov.record_usage(provider="fake", model="fake-default", usage=usage)

    usage2 = TokenUsage(
        prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.15
    )
    update2 = gov.record_usage(provider="fake", model="fake-default", usage=usage2)
    assert update2.warnings_fired_this_call == ["90"]


def test_preflight_blocks_when_worst_case_over_budget() -> None:
    gov = CostGovernor(1.0)
    gov.record_usage(
        provider="fake",
        model="fake-default",
        usage=TokenUsage(
            prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.90
        ),
    )
    result = gov.preflight(
        provider="fake",
        model="fake-default",
        prompt_tokens=10000,
        max_tokens_fallback=100000,
    )
    assert result.blocked is True
    assert "not made" in result.message
    # Governor state must NOT be mutated by preflight
    assert gov.state.spent_usd_estimate == 0.90


def test_preflight_does_not_call_client() -> None:
    gov = CostGovernor(1.0)
    result = gov.preflight(
        provider="fake",
        model="fake-default",
        prompt_tokens=100,
        max_tokens_fallback=50,
    )
    assert result.blocked is False


def test_preflight_unknown_model_does_not_block() -> None:
    gov = CostGovernor(1.0)
    result = gov.preflight(
        provider="unknown",
        model="unknown",
        prompt_tokens=100000,
        max_tokens_fallback=50000,
    )
    assert result.blocked is False


def test_preflight_zero_budget_never_blocks() -> None:
    gov = CostGovernor(0.0)
    result = gov.preflight(
        provider="fake",
        model="fake-default",
        prompt_tokens=100000,
        max_tokens_fallback=50000,
    )
    assert result.blocked is False


def test_raise_if_blocked_raises_BudgetStopError() -> None:
    from sagasmith.schemas.safety_cost import CostState

    fake_state = CostState(
        session_budget_usd=1.0,
        spent_usd_estimate=0.0,
        tokens_prompt=0,
        tokens_completion=0,
        warnings_sent=[],
        hard_stopped=False,
    )
    with pytest.raises(BudgetStopError):
        BudgetStopResult(
            blocked=True,
            cost_state=fake_state,
            worst_case_cost_usd=0.01,
            message="blocked",
        ).raise_if_blocked()

    # blocked=False does not raise
    BudgetStopResult(
        blocked=False,
        cost_state=fake_state,
        worst_case_cost_usd=0.0,
        message="",
    ).raise_if_blocked()


def test_state_property_returns_copy() -> None:
    gov = CostGovernor(1.0)
    state1 = gov.state
    state2 = gov.state
    assert state1 is not state2


def test_format_budget_inspection_math() -> None:
    gov = CostGovernor(1.0)
    gov.record_usage(
        provider="fake",
        model="fake-default",
        usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
    )
    inspection = gov.format_budget_inspection()
    assert inspection.remaining_usd == pytest.approx(0.998)
    assert inspection.fraction_used == pytest.approx(0.002)
    assert inspection.tokens_total == 1500
    assert inspection.hard_stopped is False


def test_format_budget_inspection_zero_budget_fraction() -> None:
    gov = CostGovernor(0.0)
    gov.record_usage(
        provider="fake",
        model="fake-default",
        usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
    )
    inspection = gov.format_budget_inspection()
    assert inspection.fraction_used == 0.0
