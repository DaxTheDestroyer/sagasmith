"""Tests for sagasmith.app.campaign lifecycle functions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign, slugify
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.migrations import current_schema_version


def test_init_campaign_writes_manifest_and_db(tmp_path: Path) -> None:
    root = tmp_path / "mycampaign"
    manifest = init_campaign(name="Rivermouth", root=root, provider="fake")
    assert manifest.campaign_name == "Rivermouth"
    assert manifest.manifest_version == 1
    assert (root / "campaign.toml").is_file()
    assert (root / "campaign.sqlite").is_file()
    assert (root / "player_vault").is_dir()

    # Verify the DB has schema_version == 5 (all migrations applied) and a campaign row.
    conn = open_campaign_db(root / "campaign.sqlite", read_only=True)
    try:
        assert current_schema_version(conn) == 5
        row = conn.execute(
            "SELECT campaign_name FROM campaigns WHERE campaign_id = ?",
            (manifest.campaign_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "Rivermouth"
    finally:
        conn.close()


def test_open_campaign_returns_parsed_manifest(tmp_path: Path) -> None:
    root = tmp_path / "mycampaign"
    init_campaign(name="Rivermouth", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    assert manifest.manifest_version == 1
    assert manifest.campaign_name == "Rivermouth"
    assert paths.db.is_file()
    assert paths.player_vault.is_dir()


def test_slugify_matches_validator() -> None:
    slug = slugify("Rivermouth: Part I!")
    assert slug == "rivermouth-part-i"
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", slug)


def test_slugify_truncates_to_40() -> None:
    long_name = "a" * 100
    slug = slugify(long_name)
    assert len(slug) == 40


def test_init_campaign_fails_when_dir_exists(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    with pytest.raises(FileExistsError):
        init_campaign(name="Rivermouth", root=root, provider="fake")
