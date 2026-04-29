"""Tests for vault maintenance CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sagasmith.app.campaign import init_campaign
from sagasmith.cli.main import app
from sagasmith.memory.fts5 import FTS5Index
from sagasmith.persistence.db import open_campaign_db
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter

runner = CliRunner()


def test_vault_sync_command_projects_player_vault(tmp_path: Path) -> None:
    root = tmp_path / "rivermouth"
    manifest = init_campaign(name="Rivermouth", root=root, provider="fake")
    service = VaultService(
        campaign_id=manifest.campaign_id, player_vault_root=root / "player_vault"
    )
    service.write_page(
        VaultPage(
            LoreFrontmatter(
                id="lore_known",
                type="lore",
                name="Known Lore",
                aliases=[],
                visibility="player_known",
                category="public",
                gm_notes="hidden",
            ),
            "Known public fact.\n<!-- gm: hidden detail -->",
        ),
        Path("lore/lore_known.md"),
    )

    result = runner.invoke(app, ["vault", "sync", "--campaign", str(root)])

    assert result.exit_code == 0, result.output
    assert "Player vault synced." in result.output
    player_text = (root / "player_vault" / "lore" / "lore_known.md").read_text(encoding="utf-8")
    assert "Known public fact." in player_text
    assert "gm_notes" not in player_text
    assert "<!-- gm:" not in player_text


def test_vault_rebuild_command_rebuilds_fts5(tmp_path: Path) -> None:
    root = tmp_path / "rivermouth"
    manifest = init_campaign(name="Rivermouth", root=root, provider="fake")
    service = VaultService(
        campaign_id=manifest.campaign_id, player_vault_root=root / "player_vault"
    )
    service.write_page(
        VaultPage(
            LoreFrontmatter(
                id="lore_known",
                type="lore",
                name="Known Lore",
                aliases=[],
                visibility="player_known",
                category="public",
            ),
            "The copper bridge is safe.",
        ),
        Path("lore/lore_known.md"),
    )

    result = runner.invoke(app, ["vault", "rebuild", "--campaign", str(root)])

    assert result.exit_code == 0, result.output
    assert "Vault indices rebuilt successfully." in result.output
    conn = open_campaign_db(root / "campaign.sqlite")
    try:
        assert FTS5Index(conn).query("copper")
    finally:
        conn.close()
