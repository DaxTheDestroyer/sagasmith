"""CostGovernor: deterministic cost accounting and budget enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sagasmith.schemas.safety_cost import CostState
from sagasmith.services.errors import BudgetStopError
from sagasmith.services.pricing_table import (
    PriceEntry,
    estimate_cost_from_usage,
    load_pricing_table,
)

if TYPE_CHECKING:
    from sagasmith.schemas.provider import TokenUsage


@dataclass(frozen=True)
class BudgetStopResult:
    """Result of a preflight budget check."""

    blocked: bool
    cost_state: CostState
    worst_case_cost_usd: float
    message: str

    def raise_if_blocked(self) -> None:
        if self.blocked:
            raise BudgetStopError(self.message)


@dataclass(frozen=True)
class CostUpdate:
    """Result of recording one provider call's usage."""

    cost_usd: float
    cost_is_approximate: bool
    new_state: CostState
    warnings_fired_this_call: list[Literal["70", "90"]]


@dataclass(frozen=True)
class BudgetInspection:
    """Read-only budget summary for TUI rendering."""

    session_budget_usd: float
    spent_usd_estimate: float
    remaining_usd: float
    fraction_used: float
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    unknown_cost_call_count: int
    warnings_sent: tuple[Literal["70", "90"], ...]
    hard_stopped: bool


class CostGovernor:
    """Stateful cost governor enforcing session budget and exactly-once warnings."""

    def __init__(
        self,
        session_budget_usd: float,
        *,
        pricing_table: dict[str, PriceEntry] | None = None,
    ) -> None:
        if session_budget_usd < 0:
            raise ValueError("session_budget_usd must be >= 0")
        self._session_budget_usd = session_budget_usd
        self._table = pricing_table if pricing_table is not None else load_pricing_table()
        self._spent_usd_estimate = 0.0
        self._tokens_prompt = 0
        self._tokens_completion = 0
        self._unknown_cost_call_count = 0
        self._warnings_sent: list[Literal["70", "90"]] = []
        self._hard_stopped = False

    @property
    def state(self) -> CostState:
        return CostState(
            session_budget_usd=self._session_budget_usd,
            spent_usd_estimate=self._spent_usd_estimate,
            tokens_prompt=self._tokens_prompt,
            tokens_completion=self._tokens_completion,
            unknown_cost_call_count=self._unknown_cost_call_count,
            warnings_sent=list(self._warnings_sent),
            hard_stopped=self._hard_stopped,
        )

    def record_usage(
        self,
        *,
        provider: str,
        model: str,
        usage: TokenUsage,
    ) -> CostUpdate:
        """Record token usage, update internal state, and return cost info."""
        if usage.provider_cost_usd is not None:
            cost_usd = usage.provider_cost_usd
            is_approximate = False
        else:
            try:
                cost_usd, is_approximate = estimate_cost_from_usage(
                    provider=provider,
                    model=model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    table=self._table,
                )
            except KeyError:
                # D-09: unknown cost is better than crashing gameplay
                cost_usd = 0.0
                is_approximate = True
                self._unknown_cost_call_count += 1

        self._spent_usd_estimate += cost_usd
        self._tokens_prompt += usage.prompt_tokens
        self._tokens_completion += usage.completion_tokens

        warnings_fired: list[Literal["70", "90"]] = []
        if self._session_budget_usd > 0:
            fraction = self._spent_usd_estimate / self._session_budget_usd
            if fraction >= 0.70 and "70" not in self._warnings_sent:
                self._warnings_sent.append("70")
                warnings_fired.append("70")
            if fraction >= 0.90 and "90" not in self._warnings_sent:
                self._warnings_sent.append("90")
                warnings_fired.append("90")

        new_state = self.state
        return CostUpdate(
            cost_usd=cost_usd,
            cost_is_approximate=is_approximate,
            new_state=new_state,
            warnings_fired_this_call=warnings_fired,
        )

    def preflight(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        max_tokens_fallback: int,
    ) -> BudgetStopResult:
        """Check whether a would-be call would exceed the session budget.

        This method is pure: it does not mutate internal state or call the provider.
        """
        try:
            worst_case_cost_usd, _ = estimate_cost_from_usage(
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=max_tokens_fallback,
                table=self._table,
            )
        except KeyError:
            # D-10: unknown cost means cannot confidently block
            worst_case_cost_usd = 0.0

        projected_spent = self._spent_usd_estimate + worst_case_cost_usd
        if self._session_budget_usd > 0 and projected_spent > self._session_budget_usd:
            message = (
                f"Session budget ${self._session_budget_usd:.2f} would be exceeded by the next call "
                f"(estimated +${worst_case_cost_usd:.4f}). Call not made."
            )
            projected_state = CostState(
                session_budget_usd=self._session_budget_usd,
                spent_usd_estimate=projected_spent,
                tokens_prompt=self._tokens_prompt,
                tokens_completion=self._tokens_completion,
                unknown_cost_call_count=self._unknown_cost_call_count,
                warnings_sent=list(self._warnings_sent),
                hard_stopped=True,
            )
            return BudgetStopResult(
                blocked=True,
                cost_state=projected_state,
                worst_case_cost_usd=worst_case_cost_usd,
                message=message,
            )

        projected_state = CostState(
            session_budget_usd=self._session_budget_usd,
            spent_usd_estimate=projected_spent,
            tokens_prompt=self._tokens_prompt,
            tokens_completion=self._tokens_completion,
            unknown_cost_call_count=self._unknown_cost_call_count,
            warnings_sent=list(self._warnings_sent),
            hard_stopped=False,
        )
        return BudgetStopResult(
            blocked=False,
            cost_state=projected_state,
            worst_case_cost_usd=worst_case_cost_usd,
            message="",
        )

    def apply_hard_stop(self) -> None:
        """Permanently mark the session as hard-stopped."""
        self._hard_stopped = True

    def format_budget_inspection(self) -> BudgetInspection:
        """Return a read-only budget summary for UI rendering."""
        if self._session_budget_usd > 0:
            fraction = self._spent_usd_estimate / self._session_budget_usd
            remaining = self._session_budget_usd - self._spent_usd_estimate
        else:
            fraction = 0.0
            remaining = 0.0

        return BudgetInspection(
            session_budget_usd=self._session_budget_usd,
            spent_usd_estimate=self._spent_usd_estimate,
            remaining_usd=remaining,
            fraction_used=fraction,
            tokens_prompt=self._tokens_prompt,
            tokens_completion=self._tokens_completion,
            tokens_total=self._tokens_prompt + self._tokens_completion,
            unknown_cost_call_count=self._unknown_cost_call_count,
            warnings_sent=tuple(self._warnings_sent),
            hard_stopped=self._hard_stopped,
        )
