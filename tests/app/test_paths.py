"""Tests for sagasmith.app.paths."""

from pathlib import Path

import pytest

from sagasmith.app.paths import resolve_campaign_paths, validate_campaign_paths


def test_resolve_campaign_paths_derives_all_four() -> None:
    root = Path("/tmp/foo")
    paths = resolve_campaign_paths(root)
    assert paths.root == root
    assert paths.manifest == root / "campaign.toml"
    assert paths.db == root / "campaign.sqlite"
    assert paths.player_vault == root / "player_vault"


def test_validate_campaign_paths_requires_all(tmp_path: Path) -> None:
    root = tmp_path / "mycampaign"
    root.mkdir()
    paths = resolve_campaign_paths(root)

    # Only db present — should still fail (manifest missing first)
    (root / "campaign.sqlite").write_text("")
    with pytest.raises(ValueError, match=r"campaign\.toml"):
        validate_campaign_paths(paths)

    # Add manifest — db present, vault missing
    (root / "campaign.toml").write_text("")
    with pytest.raises(ValueError, match="player_vault"):
        validate_campaign_paths(paths)

    # Add vault — now all three present
    (root / "player_vault").mkdir()
    validate_campaign_paths(paths)  # should not raise
