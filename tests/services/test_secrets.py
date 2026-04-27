"""Tests for SecretRef and resolve_secret."""

from __future__ import annotations

import pytest

from sagasmith.services.errors import SecretRefError
from sagasmith.services.secrets import SecretRef, resolve_secret, scrub_for_log

pytestmark = pytest.mark.smoke


def test_secret_ref_rejects_env_with_account() -> None:
    with pytest.raises(ValueError):
        SecretRef(kind="env", name="SOME_VAR", account="some_account")


def test_secret_ref_rejects_keyring_without_account() -> None:
    with pytest.raises(ValueError):
        SecretRef(kind="keyring", name="service", account=None)


def test_resolve_secret_env_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGASMITH_TEST_KEY", "synthetic-value-xyz")
    ref = SecretRef(kind="env", name="SAGASMITH_TEST_KEY", account=None)
    assert resolve_secret(ref) == "synthetic-value-xyz"


def test_resolve_secret_env_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAGASMITH_ABSENT_KEY", raising=False)
    ref = SecretRef(kind="env", name="SAGASMITH_ABSENT_KEY", account=None)
    with pytest.raises(SecretRefError) as exc_info:
        resolve_secret(ref)
    msg = str(exc_info.value)
    assert "SAGASMITH_ABSENT_KEY" not in msg


def test_resolve_secret_keyring_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import sagasmith.services.secrets as secrets_mod

    monkeypatch.setattr(
        secrets_mod.keyring, "get_password", lambda svc, acct: "synthetic-keyring-value"
    )
    ref = SecretRef(kind="keyring", name="service", account="user")
    assert resolve_secret(ref) == "synthetic-keyring-value"


def test_resolve_secret_keyring_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import sagasmith.services.secrets as secrets_mod

    monkeypatch.setattr(secrets_mod.keyring, "get_password", lambda svc, acct: None)
    ref = SecretRef(kind="keyring", name="service", account="user")
    with pytest.raises(SecretRefError) as exc_info:
        resolve_secret(ref)
    msg = str(exc_info.value)
    assert "keyring entry missing" in msg


def test_scrub_for_log_redacts() -> None:
    assert scrub_for_log("sk-or-v1-aaaaaaaaaaaaaaaa") == "<redacted>"
    assert scrub_for_log(None) == "<unset>"
    assert scrub_for_log("") == "<unset>"
