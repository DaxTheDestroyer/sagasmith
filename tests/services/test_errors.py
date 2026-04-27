"""Tests for trust-service errors."""

from __future__ import annotations

import pytest

from sagasmith.services.errors import (
    BudgetStopError,
    ProviderCallError,
    SecretRefError,
    TrustServiceError,
)

pytestmark = pytest.mark.smoke


def test_trust_service_error_is_exception() -> None:
    assert issubclass(TrustServiceError, Exception)


def test_specific_errors_subclass_trust_service() -> None:
    assert issubclass(SecretRefError, TrustServiceError)
    assert issubclass(BudgetStopError, TrustServiceError)
    assert issubclass(ProviderCallError, TrustServiceError)


def test_secret_ref_error_stringifies_safely() -> None:
    exc = SecretRefError(provider="openrouter", ref_kind="env", reason="env var not set")
    msg = str(exc)
    assert "provider=openrouter" in msg
    assert "ref_kind=env" in msg
    assert "reason=env var not set" in msg
    assert "sk-" not in msg
    assert "Bearer" not in msg
    assert "Authorization" not in msg


def test_secret_ref_error_properties() -> None:
    exc = SecretRefError(provider="openrouter", ref_kind="env", reason="env var not set")
    assert exc.provider == "openrouter"
    assert exc.ref_kind == "env"
    assert exc.reason == "env var not set"
