"""Typed trust-service exception hierarchy."""

from __future__ import annotations

from typing import Literal


class TrustServiceError(Exception):
    """Root for all Phase 2 deterministic-service errors."""


class SecretRefError(TrustServiceError):
    """Raised for missing/invalid secret references.

    Never includes the secret value, env var value, or authorization header.
    """

    def __init__(self, provider: str, ref_kind: Literal["keyring", "env"], reason: str) -> None:
        self._provider = provider
        self._ref_kind = ref_kind
        self._reason = reason
        super().__init__(
            f"secret reference unavailable: provider={provider} ref_kind={ref_kind} reason={reason}"
        )

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def ref_kind(self) -> Literal["keyring", "env"]:
        return self._ref_kind  # type: ignore[return-value]

    @property
    def reason(self) -> str:
        return self._reason


class BudgetStopError(TrustServiceError):
    """Raised when a pre-call budget check would exceed session_budget_usd (D-12)."""


class ProviderCallError(TrustServiceError):
    """Raised when an LLM provider call fails after the retry ladder (D-03)."""
