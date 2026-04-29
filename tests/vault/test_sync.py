"""Player vault projection sync tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.vault import VaultPage, VaultService, VaultSyncError
from sagasmith.vault.page import FactionFrontmatter, LoreFrontmatter, NpcFrontmatter


def _service(tmp_path: Path) -> VaultService:
    service = VaultService(campaign_id="sync-test", player_vault_root=tmp_path / "player")
    service.master_path = tmp_path / "master"
    service.ensure_master_path()
    return service


def test_sync_projects_known_and_foreshadowed_without_gm_leakage(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.write_page(
        VaultPage(
            NpcFrontmatter(
                id="npc_mara",
                type="npc",
                name="Mara",
                aliases=["the scout"],
                visibility="player_known",
                first_encountered="session_001",
                species="human",
                role="scout",
                status="alive",
                disposition_to_pc="friendly",
                gm_notes="Secret debt",
                secrets=["betrays the party"],
            ),
            "Mara helps the party.\n<!-- gm: she reports to the guild -->\nPublic detail.",
        ),
        Path("npcs/npc_mara.md"),
    )
    service.write_page(
        VaultPage(
            FactionFrontmatter(
                id="fac_guild",
                type="faction",
                name="River Guild",
                aliases=["the Guild"],
                visibility="foreshadowed",
                alignment="neutral",
                disposition_to_pc="unknown",
                power_level="regional",
                gm_notes="Runs the docks",
                secrets=["controls Mara"],
            ),
            "The guild controls everything.",
        ),
        Path("factions/fac_guild.md"),
    )
    service.write_page(
        VaultPage(
            LoreFrontmatter(
                id="lore_hidden",
                type="lore",
                name="Hidden Lore",
                aliases=[],
                visibility="gm_only",
                category="secret",
            ),
            "Forbidden truth.",
        ),
        Path("lore/lore_hidden.md"),
    )

    service.sync()

    known = (service.player_vault_root / "npcs/npc_mara.md").read_text(encoding="utf-8")
    assert "gm_notes" not in known
    assert "secrets" not in known
    assert "<!-- gm:" not in known
    assert "Public detail." in known

    stub = (service.player_vault_root / "factions/fac_guild.md").read_text(encoding="utf-8")
    assert "id: fac_guild" in stub
    assert "name: River Guild" in stub
    assert "alignment" not in stub
    assert "The guild controls everything" not in stub
    assert "*Unknown - you have heard this name but know little more.*" in stub

    assert not (service.player_vault_root / "lore/lore_hidden.md").exists()
    assert (service.player_vault_root / "index.md").exists()
    assert (service.player_vault_root / "log.md").exists()
    assert "Mara" in (service.player_vault_root / "index.md").read_text(encoding="utf-8")


def test_sync_removes_stale_player_projection_files(tmp_path: Path) -> None:
    service = _service(tmp_path)
    stale = service.player_vault_root / "npcs/npc_old_secret.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale spoiler", encoding="utf-8")

    service.write_page(
        VaultPage(
            LoreFrontmatter(
                id="lore_hidden",
                type="lore",
                name="Hidden Lore",
                aliases=[],
                visibility="gm_only",
                category="secret",
            ),
            "Hidden body.",
        ),
        Path("lore/lore_hidden.md"),
    )

    service.sync()

    assert not stale.exists()


def test_sync_wraps_io_failures_as_vault_sync_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
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
            "Known body.",
        ),
        Path("lore/lore_known.md"),
    )

    def fail_read_text(*args: object, **kwargs: object) -> str:
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    with pytest.raises(VaultSyncError, match="disk unavailable"):
        service.sync()
