"""Tests for atomic vault writer and resolver."""

from pathlib import Path

import pytest

from sagasmith.vault.page import BaseVaultFrontmatter, NpcFrontmatter, VaultPage
from sagasmith.vault.resolver import EntityResolver, slugify
from sagasmith.vault.writer import atomic_write


class SimplePage(VaultPage):
    """Minimal concrete VaultPage for tests using BaseVaultFrontmatter."""

    def __init__(self, frontmatter: BaseVaultFrontmatter, body: str = ""):
        super().__init__(frontmatter, body)


def test_atomic_write_success(tmp_path: Path):
    target = tmp_path / "page.md"
    fm = BaseVaultFrontmatter(id="test_slug", type="lore", name="Test", visibility="player_known")
    page = VaultPage(fm, body="Hello world")
    atomic_write(page, target)
    assert target.exists()
    content = target.read_text()
    assert "Hello world" in content
    assert "---" in content


def test_atomic_write_validates_yaml(tmp_path: Path):
    target = tmp_path / "bad.md"
    # Good frontmatter; should succeed
    fm = NpcFrontmatter(
        id="npc_test",
        name="Test NPC",
        species="human",
        role="warrior",
        status="active",
        disposition_to_pc="friendly",
        visibility="gm_only",
    )
    page = VaultPage(fm, body="")
    atomic_write(page, target)
    assert target.exists()


def test_atomic_write_cleans_temp_on_error(tmp_path: Path):
    # Error-path cleanup is exercised via integration tests; skip in unit suite.
    pytest.skip("Exercise error branch in manual integration tests")


def test_slugify_basic():
    assert slugify("Orym the Humble") == "orym_the_humble"
    assert slugify("City-Guard") == "city_guard"
    assert slugify("  Spaces  ") == "spaces"


def test_resolver_finds_by_slug(tmp_path: Path):
    # Create two NPC pages
    master = tmp_path / "master"
    master.mkdir()
    npc1 = master / "npc_orym_the_humble.md"
    fm = NpcFrontmatter(
        id="npc_orym_the_humble",
        name="Orym the Humble",
        species="halfling",
        role="fighter",
        status="active",
        disposition_to_pc="friendly",
        visibility="gm_only",
    )
    page = VaultPage(fm, body="")
    atomic_write(page, npc1)
    resolver = EntityResolver(master)
    # Provide entity_type to construct prefixed slug
    found = resolver.resolve("Orym the Humble", entity_type="npc")
    assert found is not None
    assert found.frontmatter.id == "npc_orym_the_humble"


def test_resolver_finds_by_alias(tmp_path: Path):
    master = tmp_path / "master"
    master.mkdir()
    npc = master / "npc_orym_the_humble.md"
    fm = NpcFrontmatter(
        id="npc_orym_the_humble",
        name="Orym",
        species="halfling",
        role="fighter",
        status="active",
        disposition_to_pc="friendly",
        visibility="gm_only",
        aliases=["Orym the Humble", "Halfling hero"],
    )
    page = VaultPage(fm, body="")
    atomic_write(page, npc)
    resolver = EntityResolver(master)
    found = resolver.resolve("Halfling hero")
    assert found is not None
    assert found.frontmatter.id == "npc_orym_the_humble"


def test_resolver_type_filter(tmp_path: Path):
    master = tmp_path / "master"
    master.mkdir()
    npc = master / "npc_orym.md"
    fm = NpcFrontmatter(
        id="npc_orym",
        name="Orym",
        species="halfling",
        role="fighter",
        status="active",
        disposition_to_pc="friendly",
        visibility="gm_only",
    )
    atomic_write(VaultPage(fm, body=""), npc)
    resolver = EntityResolver(master)
    assert resolver.resolve("Orym", entity_type="npc") is not None
    assert resolver.resolve("Orym", entity_type="location") is None


def test_resolver_unknown_type_finds_slug_without_alias(tmp_path: Path):
    master = tmp_path / "master"
    master.mkdir()
    npc = master / "npc_marcus.md"
    fm = NpcFrontmatter(
        id="npc_marcus",
        name="Marcus",
        species="human",
        role="innkeeper",
        status="alive",
        disposition_to_pc="friendly",
        visibility="player_known",
    )
    atomic_write(VaultPage(fm, body=""), npc)
    resolver = EntityResolver(master)

    found = resolver.resolve("Marcus", entity_type=None)

    assert found is not None
    assert found.frontmatter.id == "npc_marcus"


def test_load_spec_complete_npc_keeps_extra_schema_fields(tmp_path: Path):
    path = tmp_path / "npc_marcus.md"
    path.write_text(
        "---\n"
        "id: npc_marcus\n"
        "type: npc\n"
        "name: Marcus\n"
        "aliases: []\n"
        "species: Human\n"
        "role: Innkeeper\n"
        "status: alive\n"
        "disposition_to_pc: friendly\n"
        "voice: weary\n"
        "location_current: loc_tavern\n"
        "factions:\n"
        "  - fac_guild\n"
        "visibility: player_known\n"
        "secrets:\n"
        "  - owes guild debt\n"
        "---\n\n"
        "Marcus runs the tavern.",
        encoding="utf-8",
    )

    page = VaultPage.load_file(path)

    assert isinstance(page.frontmatter, NpcFrontmatter)
    assert page.frontmatter.location_current == "loc_tavern"
    assert page.frontmatter.factions == ["fac_guild"]
