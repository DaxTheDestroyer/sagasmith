"""Tests for the ``sagasmith onboard`` CLI command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.cli.main import app
from sagasmith.onboarding.store import OnboardingStore
from sagasmith.persistence.db import open_campaign_db

runner = CliRunner()


def _init_campaign(tmp_path: Path) -> Path:
    root = tmp_path / "rivermouth"
    init_campaign(name="Rivermouth", root=root, provider="fake")
    return root


def _onboard_args(root: Path, *, pacing: str = "medium") -> list[str]:
    return [
        "onboard",
        "--campaign", str(root),
        "--genre", "high_fantasy,dark_fantasy",
        "--tone", "grim,hopeful",
        "--touchstones", "Pathfinder Core Rulebook,Dragon Age Origins",
        "--pillar-combat", "3",
        "--pillar-exploration", "3",
        "--pillar-social", "3",
        "--pillar-puzzle", "1",
        "--pacing", pacing,
        "--dice-ux", "reveal",
        "--hard-limits", "sexual_content",
        "--soft-limits", "graphic_violence:fade_to_black",
        "--preferences", "heroic_sacrifice,moral_ambiguity",
        "--campaign-length", "arc",
        "--death-policy", "heroic_recovery",
        "--per-session-usd", "2.50",
        "--character-mode", "pregenerated",
        "--yes",
    ]


def test_onboard_commits_validated_triple(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    result = runner.invoke(app, _onboard_args(root))

    assert result.exit_code == 0, result.output
    assert "Onboarding review:" in result.output
    assert "Onboarding committed" in result.output

    _paths, manifest = open_campaign(root)
    conn = open_campaign_db(root / "campaign.sqlite", read_only=True)
    try:
        triple = OnboardingStore(conn).reload(manifest.campaign_id)
    finally:
        conn.close()

    assert triple is not None
    assert triple.player_profile.pacing == "medium"
    assert triple.content_policy.hard_limits == ["sexual_content"]
    assert triple.house_rules.dice_ux == "reveal"


def test_onboard_requires_yes_in_noninteractive_mode(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    args = _onboard_args(root)
    args.remove("--yes")

    result = runner.invoke(app, args)

    assert result.exit_code == 2
    assert "--yes is required" in result.output


def test_onboard_rerun_overwrites_existing_triple(tmp_path: Path) -> None:
    root = _init_campaign(tmp_path)
    assert runner.invoke(app, _onboard_args(root, pacing="medium")).exit_code == 0
    result = runner.invoke(app, _onboard_args(root, pacing="fast"))

    assert result.exit_code == 0, result.output

    _paths, manifest = open_campaign(root)
    conn = open_campaign_db(root / "campaign.sqlite", read_only=True)
    try:
        triple = OnboardingStore(conn).reload(manifest.campaign_id)
    finally:
        conn.close()

    assert triple is not None
    assert triple.player_profile.pacing == "fast"
