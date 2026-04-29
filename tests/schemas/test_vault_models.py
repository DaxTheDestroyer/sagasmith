"""Tests for vault frontmatter models."""

import pytest

from sagasmith.vault.page import (
    BaseVaultFrontmatter,
    CallbackFrontmatter,
    FactionFrontmatter,
    ItemFrontmatter,
    LocationFrontmatter,
    LoreFrontmatter,
    NpcFrontmatter,
    QuestFrontmatter,
    SessionFrontmatter,
)


def test_base_frontmatter_minimal():
    fm = BaseVaultFrontmatter(id="test", type="lore", name="Test", visibility="player_known")
    assert fm.id == "test"


def test_npc_frontmatter_requires_fields():
    npc = NpcFrontmatter(
        id="npc_orym",
        name="Orym the Humble",
        species="halfling",
        role="fighter",
        status="active",
        disposition_to_pc="friendly",
        visibility="gm_only",
    )
    assert npc.type == "npc"
    assert npc.species == "halfling"


def test_location_frontmatter():
    loc = LocationFrontmatter(
        id="loc_haven",
        name="Haven",
        status="safe",
        visibility="player_known",
    )
    assert loc.connects_to == []


def test_faction_frontmatter():
    fac = FactionFrontmatter(
        id="faction_guard",
        name="City Guard",
        alignment="lawful_good",
        disposition_to_pc="neutral",
        power_level="local",
    )
    assert fac.type == "faction"


def test_item_frontmatter():
    item = ItemFrontmatter(
        id="item_sword",
        name="Longsword",
        rarity="common",
    )
    assert item.rarity == "common"


def test_quest_frontmatter():
    quest = QuestFrontmatter(
        id="quest_001",
        name="Goblin menace",
        status="active",
    )
    assert quest.callbacks == []


def test_callback_frontmatter():
    cb = CallbackFrontmatter(
        id="cb_seed1",
        name="Debt collector",
        status="open",
    )
    assert cb.seeded_in is None


def test_session_frontmatter():
    sess = SessionFrontmatter(
        id="session_1",
        name="Session 1",
        number=1,
        date_real="2026-04-28",
        date_in_game="4691-01-01",
    )
    assert sess.number == 1


def test_lore_frontmatter():
    lore = LoreFrontmatter(
        id="lore_world",
        name="World History",
        category="history",
    )
    assert lore.category == "history"


def test_frontmatter_missing_required_raises():
    with pytest.raises(Exception):
        NpcFrontmatter(
            id="incomplete",
            name="Incomplete",
            # missing species, role, status, disposition_to_pc
            visibility="gm_only",
        )  # type: ignore[call-arg]
