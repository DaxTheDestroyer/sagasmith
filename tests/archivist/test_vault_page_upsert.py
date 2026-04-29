"""Tests for vault-page-upsert skill."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.agents.archivist.skills.vault_page_upsert.logic import (
    vault_page_upsert,
)
from sagasmith.vault import VaultService
from sagasmith.vault.page import NpcFrontmatter


@pytest.fixture
def vault_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VaultService:
    # Patch the default master vault root to point inside tmp_path for isolation
    import sagasmith.vault.paths as vp

    monkeypatch.setattr(vp, "DEFAULT_MASTER_OPTS", tmp_path / ".ttrpg" / "vault")

    campaign_id = "test_campaign"
    player_vault_root = tmp_path / "player_vault"
    service = VaultService(campaign_id=campaign_id, player_vault_root=player_vault_root)
    service.ensure_master_path()
    service.ensure_player_vault()
    return service


def test_vault_page_upsert_creates_npc_page(vault_service: VaultService, tmp_path: Path) -> None:
    draft = {
        "name": " test_character ",
        "type": "npc",
        "species": "human",
        "role": "merchant",
        "status": "alive",
        "disposition_to_pc": "friendly",
    }
    result = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft,
        visibility="player_known",
        session_number=1,
    )
    assert result.action == "created"
    assert result.relative_path == Path("npcs") / "npc_test_character.md"
    assert not (vault_service.master_path / result.relative_path).exists()
    page = result.page
    assert isinstance(page.frontmatter, NpcFrontmatter)
    assert page.frontmatter.name == "test_character"
    assert page.frontmatter.visibility == "player_known"
    assert page.frontmatter.first_encountered == "1"
    assert page.frontmatter.species == "human"


def test_vault_page_upsert_slug_collision_adds_suffix(vault_service: VaultService) -> None:
    draft = {
        "name": "Marcus",
        "type": "npc",
        "species": "human",
        "role": "innkeeper",
        "status": "alive",
        "disposition_to_pc": "friendly",
    }
    # First write
    result1 = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft,
        visibility="gm_only",
        session_number=1,
    )
    assert result1.action == "created"
    vault_service.write_page(result1.page, result1.relative_path)
    # Second write with same name but different species triggers collision _2
    draft2 = dict(draft)
    draft2["species"] = "elf"
    result2 = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft2,
        visibility="gm_only",
        session_number=1,
    )
    assert result2.action == "created"
    assert result2.relative_path.name == "npc_marcus_2.md"
    assert result2.page.frontmatter.id == "npc_marcus_2"
    vault_service.write_page(result2.page, result2.relative_path)
    # Third write same name → _3
    draft3 = dict(draft)
    draft3["species"] = "dwarf"
    result3 = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft3,
        visibility="gm_only",
        session_number=1,
    )
    assert result3.action == "created"
    assert result3.relative_path.name == "npc_marcus_3.md"
    assert result3.page.frontmatter.id == "npc_marcus_3"


def test_vault_page_upsert_invalid_draft_raises(vault_service: VaultService) -> None:
    # Missing name should raise
    draft = {"type": "npc"}
    with pytest.raises(ValueError, match="non-empty 'name'"):
        vault_page_upsert(
            vault_service=vault_service,
            entity_draft=draft,
            visibility="gm_only",
            session_number=1,
        )
    # Missing type should raise
    draft = {"name": "Bob"}
    with pytest.raises(ValueError, match="string 'type'"):
        vault_page_upsert(
            vault_service=vault_service,
            entity_draft=draft,
            visibility="gm_only",
            session_number=1,
        )


def test_vault_page_upsert_update_existing(vault_service: VaultService) -> None:
    # Create first
    draft = {
        "name": "Orym",
        "type": "npc",
        "species": "human",
        "role": "fighter",
        "status": "alive",
        "disposition_to_pc": "friendly",
    }
    result1 = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft,
        visibility="gm_only",
        session_number=1,
    )
    vault_service.write_page(result1.page, result1.relative_path)
    # Update by providing the same slug as id (full prefixed)
    draft_update = {
        "id": "npc_orym",  # full prefixed id
        "name": "Orym the Brave",
        "type": "npc",
        "species": "human",
        "role": "champion",
        "status": "alive",
        "disposition_to_pc": "ally",
    }
    result2 = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft_update,
        visibility="player_known",
        session_number=2,
    )
    assert result2.action == "updated"
    assert result2.relative_path.name == "npc_orym.md"
    page = result2.page
    assert page.frontmatter.name == "Orym the Brave"
    assert page.frontmatter.role == "champion"
    assert page.frontmatter.visibility == "player_known"
    assert page.frontmatter.first_encountered == "1"  # original first_encountered unchanged (not updated)


def test_vault_page_upsert_location(vault_service: VaultService) -> None:
    draft = {
        "name": "Rivermouth",
        "type": "location",
        "settlement": "town",
        "region": "coastal",
        "status": "active",
    }
    result = vault_page_upsert(
        vault_service=vault_service,
        entity_draft=draft,
        visibility="player_known",
        session_number=1,
    )
    assert result.action == "created"
    from sagasmith.vault.page import LocationFrontmatter

    page = result.page
    assert isinstance(page.frontmatter, LocationFrontmatter)
    assert page.frontmatter.settlement == "town"
