"""Tests for Provider Runtime startup composition."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign
from sagasmith.app.config import SettingsRepository
from sagasmith.persistence.db import open_campaign_db
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.providers.openrouter import OpenRouterClient
from sagasmith.providers.runtime import build_provider_runtime
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.services.secrets import SecretRef
from tests.providers.conftest import FakeHttpTransport


def _open_db(root: Path) -> sqlite3.Connection:
    return open_campaign_db(root / "campaign.sqlite")


def test_provider_runtime_builds_fake_adapter(tmp_path: Path) -> None:
    root = tmp_path / "fake-campaign"
    manifest = init_campaign(name="Fake Campaign", root=root, provider="fake")
    conn = _open_db(root)
    try:
        result = build_provider_runtime(conn, manifest.campaign_id)
    finally:
        conn.close()

    assert result.error is None
    assert result.runtime is not None
    assert isinstance(result.runtime.client, DeterministicFakeClient)
    assert result.runtime.config.provider == "fake"
    assert result.runtime.config.api_key_ref is None


def test_provider_runtime_ignores_fake_api_key_ref(tmp_path: Path) -> None:
    root = tmp_path / "fake-key-campaign"
    manifest = init_campaign(name="Fake Key Campaign", root=root, provider="fake")
    conn = _open_db(root)
    try:
        SettingsRepository(conn).put_provider_settings(
            manifest.campaign_id,
            ProviderSettings(
                provider="fake",
                api_key_ref=SecretRef(kind="env", name="SHOULD_NOT_BE_RESOLVED"),
                default_model="fake/default",
                narration_model="fake/narration",
                cheap_model="fake/cheap",
            ),
        )
        result = build_provider_runtime(conn, manifest.campaign_id)
    finally:
        conn.close()

    assert result.error is None
    assert result.runtime is not None
    assert result.runtime.config.provider == "fake"
    assert result.runtime.config.api_key_ref is None


def test_provider_runtime_builds_openrouter_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "openrouter-campaign"
    monkeypatch.setenv("SAGASMITH_OPENROUTER_TEST_KEY", "sk-or-v1-test")
    manifest = init_campaign(
        name="OpenRouter Campaign",
        root=root,
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="SAGASMITH_OPENROUTER_TEST_KEY"),
    )
    conn = _open_db(root)
    try:
        result = build_provider_runtime(
            conn,
            manifest.campaign_id,
            transport=FakeHttpTransport(),
        )
    finally:
        conn.close()

    assert result.error is None
    assert result.runtime is not None
    assert isinstance(result.runtime.client, OpenRouterClient)
    assert result.runtime.config.provider == "openrouter"


def test_provider_runtime_returns_safe_error_for_missing_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "missing-secret-campaign"
    monkeypatch.delenv("SAGASMITH_MISSING_OPENROUTER_KEY", raising=False)
    manifest = init_campaign(
        name="Missing Secret Campaign",
        root=root,
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="SAGASMITH_MISSING_OPENROUTER_KEY"),
    )
    conn = _open_db(root)
    try:
        result = build_provider_runtime(conn, manifest.campaign_id)
    finally:
        conn.close()

    assert result.runtime is None
    assert result.error is not None
    assert result.error.kind == "secret_unavailable"
    assert "OpenRouter credentials" in result.error.message
    assert "SAGASMITH_MISSING_OPENROUTER_KEY" not in result.error.message
    assert "SAGASMITH_MISSING_OPENROUTER_KEY" not in (result.error.detail or "")
