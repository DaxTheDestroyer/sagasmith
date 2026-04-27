"""Tests for the ``sagasmith play`` CLI command."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from sagasmith.app.campaign import init_campaign
from sagasmith.cli.main import app

runner = CliRunner()


def test_play_on_fresh_campaign_prints_status_line(tmp_path: Path) -> None:
    root = tmp_path / "rivermouth"
    init_campaign(name="Rivermouth", root=root, provider="fake")
    result = runner.invoke(app, ["play", "--campaign", str(root)])
    assert result.exit_code == 0, result.output
    assert re.search(r"Campaign: Rivermouth · Session: 1 · Last turn: none", result.output)


def test_play_on_missing_campaign_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["play", "--campaign", str(tmp_path / "nonexistent")])
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "missing" in combined.lower() or "error" in combined.lower()


def test_play_on_partial_campaign_exits_2(tmp_path: Path) -> None:
    root = tmp_path / "partial"
    root.mkdir()
    # Only write the manifest (skip sqlite + vault)
    (root / "campaign.toml").write_text(
        'manifest_version = 1\ncampaign_id = "x-00000000"\ncampaign_name = "X"\n'
        'campaign_slug = "x"\ncreated_at = "2026-01-01T00:00:00Z"\n'
        'sagasmith_version = "0.1.0"\nschema_version = 2\n',
        encoding="utf-8",
    )
    result = runner.invoke(app, ["play", "--campaign", str(root)])
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    # Should mention campaign.sqlite as the missing component
    assert "campaign.sqlite" in combined or "error" in combined.lower()
