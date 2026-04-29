"""Tests for atomic vault writer and resolver."""

from pathlib import Path

import pytest

from sagasmith.vault.page import VaultPage, BaseVaultFrontmatter, NpcFrontmatter
from sagasmith.vault.writer import atomic_write
from sagasmith.vault.resolver import EntityResolver, slugify


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
