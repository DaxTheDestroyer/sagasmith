"""Layered no-paid-call MVP smoke harness tests."""

from __future__ import annotations

import os

import pytest

from sagasmith.evals import harness


pytestmark = pytest.mark.smoke


MVP_CHECK_NAMES = [
    "mvp.install_entrypoint",
    "mvp.init",
    "mvp.configure_fake",
    "mvp.onboard",
    "mvp.play_skill_challenge",
    "mvp.play_simple_combat",
    "mvp.quit",
    "mvp.resume",
]


def test_run_mvp_smoke_returns_all_named_ok_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = harness.run_mvp_smoke()

    assert result.ok, result.format()
    assert [check.name for check in result.checks] == MVP_CHECK_NAMES
    assert all(check.ok for check in result.checks)


def test_run_mvp_smoke_uses_fake_provider_without_openrouter_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_REF", raising=False)

    result = harness.run_mvp_smoke()
    formatted = result.format()

    assert result.ok, formatted
    assert os.environ.get("OPENROUTER_API_KEY") is None
    assert "openrouter" not in formatted.lower()
    assert "api_key" not in formatted.lower()


def test_mvp_smoke_failure_includes_step_name_and_non_secret_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_init(context: object) -> str:
        raise RuntimeError("temporary campaign fixture missing")

    monkeypatch.setattr(harness, "_mvp_init", fail_init)

    result = harness.run_mvp_smoke()
    formatted = result.format()

    assert not result.ok
    assert "FAIL mvp.init" in formatted
    assert "temporary campaign fixture missing" in formatted
    assert "sk-" not in formatted
    assert "api_key" not in formatted.lower()
