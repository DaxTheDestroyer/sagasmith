"""TUI startup integration for Provider Runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.services.secrets import SecretRef
from sagasmith.tui.runtime import build_app


def test_build_app_injects_fake_provider_runtime(tmp_path: Path) -> None:
    root = tmp_path / "fake-tui"
    init_campaign(name="Fake TUI", root=root, provider="fake")

    app = build_app(root)

    assert app.graph_runtime is not None
    services = app.graph_runtime.bootstrap.services
    assert isinstance(services.llm, DeterministicFakeClient)
    assert services.provider_config is not None
    assert services.provider_config.provider == "fake"


def test_build_app_blocks_openrouter_with_missing_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "blocked-openrouter-tui"
    monkeypatch.delenv("SAGASMITH_TUI_MISSING_KEY", raising=False)
    init_campaign(
        name="Blocked OpenRouter TUI",
        root=root,
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="SAGASMITH_TUI_MISSING_KEY"),
    )

    with pytest.raises(ValueError, match="OpenRouter credentials"):
        build_app(root)
