"""Tests for the ``sagasmith init`` CLI command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sagasmith.cli.main import app
from sagasmith.persistence.db import open_campaign_db
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.services.secrets import SecretRef

runner = CliRunner()


def test_init_creates_all_artifacts_with_args(tmp_path: Path) -> None:
    target = tmp_path / "rm"
    result = runner.invoke(
        app, ["init", "--name", "Rivermouth", "--path", str(target), "--provider", "fake"]
    )
    assert result.exit_code == 0, result.output
    assert (target / "campaign.toml").is_file()
    assert (target / "campaign.sqlite").is_file()
    assert (target / "player_vault").is_dir()
    assert "Initialized campaign" in result.output


def test_init_requires_name_in_non_interactive_mode(tmp_path: Path) -> None:
    # CliRunner stdin is non-TTY by default
    result = runner.invoke(app, ["init", "--path", str(tmp_path / "x")])
    assert result.exit_code == 2
    # Check either stdout or stderr
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "--name is required" in combined


def test_init_requires_api_key_env_for_openrouter_non_interactive(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--name",
            "Rivermouth",
            "--path",
            str(tmp_path / "rm"),
            "--provider",
            "openrouter",
        ],
    )
    assert result.exit_code == 2


def test_init_persists_provider_settings(tmp_path: Path) -> None:
    target = tmp_path / "rm"
    result = runner.invoke(
        app,
        [
            "init",
            "--name",
            "Rivermouth",
            "--path",
            str(target),
            "--provider",
            "openrouter",
            "--api-key-env",
            "OPENROUTER_KEY",
        ],
    )
    assert result.exit_code == 0, result.output

    conn = open_campaign_db(target / "campaign.sqlite", read_only=True)
    try:
        row = conn.execute("SELECT value_json FROM settings WHERE key = 'provider'").fetchone()
        assert row is not None
        settings = ProviderSettings.model_validate_json(row[0])
        assert settings.api_key_ref == SecretRef(kind="env", name="OPENROUTER_KEY")
    finally:
        conn.close()


def test_init_existing_dir_exits_nonzero(tmp_path: Path) -> None:
    target = tmp_path / "rm"
    target.mkdir()
    result = runner.invoke(app, ["init", "--name", "Rivermouth", "--path", str(target)])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "already exists" in combined
