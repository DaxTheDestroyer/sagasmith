"""Tests for user-facing campaign reference resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign
from sagasmith.app.campaign_ref import open_campaign_ref


def test_open_campaign_ref_accepts_display_name(tmp_path: Path) -> None:
    root = tmp_path / "test-the-brave1"
    init_campaign(name="Test the Brave1", root=root, provider="fake")

    opened = open_campaign_ref(Path("Test the Brave1"), search_root=tmp_path)

    assert opened.paths.root == root
    assert opened.manifest.campaign_name == "Test the Brave1"


def test_open_campaign_ref_accepts_slug(tmp_path: Path) -> None:
    root = tmp_path / "test-the-brave1"
    init_campaign(name="Test the Brave1", root=root, provider="fake")

    opened = open_campaign_ref(Path("test-the-brave1"), search_root=tmp_path)

    assert opened.paths.root == root


def test_open_campaign_ref_preserves_invalid_existing_path_error(tmp_path: Path) -> None:
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "campaign.toml").write_text(
        'manifest_version = 1\ncampaign_id = "x-00000000"\ncampaign_name = "X"\n'
        'campaign_slug = "x"\ncreated_at = "2026-01-01T00:00:00Z"\n'
        'sagasmith_version = "0.1.0"\nschema_version = 2\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"campaign\.sqlite"):
        open_campaign_ref(partial, search_root=tmp_path)


def test_open_campaign_ref_rejects_ambiguous_display_name(tmp_path: Path) -> None:
    init_campaign(name="Duplicate Name", root=tmp_path / "one", provider="fake")
    init_campaign(name="Duplicate Name", root=tmp_path / "two", provider="fake")

    with pytest.raises(ValueError, match="ambiguous"):
        open_campaign_ref(Path("Duplicate Name"), search_root=tmp_path)
