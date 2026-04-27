"""Tests for the ``sagasmith configure`` CLI command."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from sagasmith.app.campaign import init_campaign
from sagasmith.cli.main import app
from sagasmith.persistence.db import open_campaign_db
from sagasmith.schemas.campaign import ProviderSettings

runner = CliRunner()


def _init_campaign(tmp_path: Path, *, name: str = "Rivermouth") -> Path:
    root = tmp_path / name.lower()
    init_campaign(name=name, root=root, provider="fake")
    return root


def test_configure_parses_env_ref(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    result = runner.invoke(
        app,
        ["configure", "--campaign", str(root), "--api-key-ref", "env:NEW_KEY"],
    )
    assert result.exit_code == 0, result.output

    # Verify the DB was updated
    conn = open_campaign_db(root / "campaign.sqlite", read_only=True)
    try:
        row = conn.execute("SELECT value_json FROM settings WHERE key = 'provider'").fetchone()
        assert row is not None
        settings = ProviderSettings.model_validate_json(row[0])
        assert settings.api_key_ref is not None
        assert settings.api_key_ref.kind == "env"
        assert settings.api_key_ref.name == "NEW_KEY"
    finally:
        conn.close()


def test_configure_parses_keyring_ref(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    result = runner.invoke(
        app,
        ["configure", "--campaign", str(root), "--api-key-ref", "keyring:openrouter:alice"],
    )
    assert result.exit_code == 0, result.output

    conn = open_campaign_db(root / "campaign.sqlite", read_only=True)
    try:
        row = conn.execute("SELECT value_json FROM settings WHERE key = 'provider'").fetchone()
        assert row is not None
        settings = ProviderSettings.model_validate_json(row[0])
        assert settings.api_key_ref is not None
        assert settings.api_key_ref.kind == "keyring"
        assert settings.api_key_ref.name == "openrouter"
        assert settings.api_key_ref.account == "alice"
    finally:
        conn.close()


def test_configure_rejects_malformed_ref(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    result = runner.invoke(
        app,
        ["configure", "--campaign", str(root), "--api-key-ref", "just-a-string"],
    )
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "must be 'env:VAR' or 'keyring:service:account'" in combined


def test_configure_rejects_openrouter_without_key_ref(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    result = runner.invoke(
        app,
        ["configure", "--campaign", str(root), "--provider", "openrouter"],
    )
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "--api-key-ref is required" in combined


def test_configure_never_echoes_secret(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    # Set the env var to a secret value — configure should only store the reference name,
    # never resolve or echo the secret value.
    env = {**os.environ, "OPENROUTER_KEY": "sk-proj-leaky"}
    result = runner.invoke(
        app,
        ["configure", "--campaign", str(root), "--api-key-ref", "env:OPENROUTER_KEY"],
        env=env,
    )
    assert result.exit_code == 0, result.output
    assert "sk-proj-leaky" not in result.output
    # Check stderr too if available
    if hasattr(result, "stderr"):
        assert "sk-proj-leaky" not in (result.stderr or "")
