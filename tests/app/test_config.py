"""Tests for sagasmith.app.config (SettingsRepository)."""

from __future__ import annotations

import sqlite3

import pytest
from pydantic import BaseModel

from sagasmith.app.config import SettingsRepository
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.services.errors import TrustServiceError
from sagasmith.services.secrets import SecretRef


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn


def _seed_campaign(conn: sqlite3.Connection, campaign_id: str = "c1") -> None:
    conn.execute(
        """
        INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (campaign_id, "Test Campaign", "test-campaign", "2026-01-01T00:00:00Z", "0.1.0"),
    )
    conn.commit()


def test_put_provider_settings_round_trips() -> None:
    conn = _make_conn()
    _seed_campaign(conn)
    repo = SettingsRepository(conn)
    settings = ProviderSettings(
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="OPENROUTER_KEY"),
        default_model="openrouter/nousresearch/hermes-2-pro-llama-3-8b",
        narration_model="openrouter/meta-llama/llama-3.1-8b-instruct",
        cheap_model="openrouter/mistralai/mistral-7b-instruct",
    )
    repo.put_provider_settings("c1", settings)
    loaded = repo.get_provider_settings("c1")
    assert loaded is not None
    assert loaded == settings


def test_put_rejects_raw_secret_payload() -> None:
    conn = _make_conn()
    _seed_campaign(conn)
    repo = SettingsRepository(conn)

    class LeakyModel(BaseModel):
        text: str

    # "sk-proj-leaky" matches the openai_project_key RedactionCanary pattern
    leaky = LeakyModel(text="sk-proj-leakysecretvaluehere12345")
    with pytest.raises(TrustServiceError, match="secret-shaped payload"):
        repo.put("c1", "leak", leaky)


def test_get_missing_returns_none() -> None:
    conn = _make_conn()
    _seed_campaign(conn)
    repo = SettingsRepository(conn)
    result = repo.get_provider_settings("c1")
    assert result is None
