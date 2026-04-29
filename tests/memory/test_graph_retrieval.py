"""Unit tests for NetworkX graph loader and neighbor query."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.memory.graph import VaultGraph, reset_vault_graph_cache, warm_vault_graph


@pytest.fixture(autouse=True)
def _clean_graph_cache():
    """Ensure graph cache is clean before and after each test."""
    reset_vault_graph_cache()
    yield
    reset_vault_graph_cache()


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal vault with interconnected pages."""
    npcs = tmp_path / "npcs"
    locs = tmp_path / "locations"
    facs = tmp_path / "factions"
    quests = tmp_path / "quests"
    callbacks = tmp_path / "callbacks"
    items = tmp_path / "items"
    for d in (npcs, locs, facs, quests, callbacks, items):
        d.mkdir()

    (npcs / "npc_marcus.md").write_text(
        "---\nid: npc_marcus\ntype: npc\nname: Marcus\nvisibility: player_known\n"
        "location_current: loc_tavern\nfactions:\n  - fac_guild\n---\n\n"
        "Marcus runs the [[loc_tavern|tavern]]. He is allied with [[fac_guild]].",
        encoding="utf-8",
    )
    (locs / "loc_tavern.md").write_text(
        "---\nid: loc_tavern\ntype: location\nname: Tavern\nvisibility: player_known\n"
        "connects_to:\n  - loc_market\n---\n\n"
        "A cozy tavern near the [[loc_market|market]].",
        encoding="utf-8",
    )
    (locs / "loc_market.md").write_text(
        "---\nid: loc_market\ntype: location\nname: Market\nvisibility: player_known\n"
        "connects_to:\n  - loc_tavern\n---\n\nThe bustling market square.",
        encoding="utf-8",
    )
    (facs / "fac_guild.md").write_text(
        "---\nid: fac_guild\ntype: faction\nname: Guild\nvisibility: foreshadowed\n"
        "known_members:\n  - npc_marcus\n---\n\nA powerful guild.",
        encoding="utf-8",
    )
    (quests / "quest_missing.md").write_text(
        "---\nid: quest_missing\ntype: quest\nname: Missing Merchant\nvisibility: player_known\n"
        "related_entities:\n  - npc_marcus\n  - loc_market\n---\n\nFind the missing merchant.",
        encoding="utf-8",
    )
    (callbacks / "cb_witness.md").write_text(
        "---\nid: cb_witness\ntype: callback\nname: Witness\nstatus: open\nvisibility: player_known\n"
        "related_quest: quest_missing\n---\n\nA witness was seen at the market.",
        encoding="utf-8",
    )
    (items / "item_map.md").write_text(
        "---\nid: item_map\ntype: item\nname: Crude Map\nvisibility: player_known\n"
        "held_by: npc_marcus\ngiven_by: npc_sera\n---\n\nA hand-drawn map.",
        encoding="utf-8",
    )
    return tmp_path


class TestVaultGraph:
    def test_load_from_vault(self, vault_root: Path) -> None:
        """Graph loads all pages as nodes."""
        graph = VaultGraph()
        count = graph.load_from_vault(vault_root)
        assert count == 7
        # Nodes include loaded pages plus implicit targets from edge references (e.g. npc_sera)
        assert len(graph.get_all_node_ids()) >= 7

    def test_wikilink_edges(self, vault_root: Path) -> None:
        """Wikilinks create directed edges."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        # npc_marcus links to loc_tavern and fac_guild via wikilinks
        assert "loc_tavern" in graph.graph.successors("npc_marcus")
        assert "fac_guild" in graph.graph.successors("npc_marcus")

    def test_connects_to_edges(self, vault_root: Path) -> None:
        """Location connects_to creates bidirectional traversal via BFS."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        # loc_tavern connects_to loc_market
        assert "loc_market" in graph.graph.successors("loc_tavern")
        # loc_market connects_to loc_tavern
        assert "loc_tavern" in graph.graph.successors("loc_market")

    def test_faction_known_members(self, vault_root: Path) -> None:
        """Faction known_members creates faction->NPC edges."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        assert "npc_marcus" in graph.graph.successors("fac_guild")

    def test_quest_related_entities(self, vault_root: Path) -> None:
        """Quest related_entities creates quest->entity edges."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        successors = list(graph.graph.successors("quest_missing"))
        assert "npc_marcus" in successors
        assert "loc_market" in successors

    def test_callback_related_quest(self, vault_root: Path) -> None:
        """Callback related_quest creates callback->quest edge."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        assert "quest_missing" in graph.graph.successors("cb_witness")

    def test_item_held_by_and_given_by(self, vault_root: Path) -> None:
        """Item held_by and given_by create edges."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        successors = list(graph.graph.successors("item_map"))
        assert "npc_marcus" in successors
        assert "npc_sera" in successors

    def test_npc_factions_and_location(self, vault_root: Path) -> None:
        """NPC factions and location_current create edges."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        successors = list(graph.graph.successors("npc_marcus"))
        assert "fac_guild" in successors
        assert "loc_tavern" in successors

    def test_get_neighbors_depth_1(self, vault_root: Path) -> None:
        """1-hop neighbors return direct connections."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        neighbors = graph.get_neighbors("npc_marcus", depth=1)
        # npc_marcus has edges to loc_tavern, fac_guild (from wikilinks + factions + location_current)
        assert "loc_tavern" in neighbors
        assert "fac_guild" in neighbors
        # loc_market is not a direct neighbor of npc_marcus
        assert "npc_marcus" not in neighbors  # self excluded

    def test_get_neighbors_depth_2(self, vault_root: Path) -> None:
        """2-hop neighbors include second-degree connections."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        neighbors = graph.get_neighbors("npc_marcus", depth=2)
        # Through loc_tavern -> loc_market (connects_to) and through wikilinks
        assert "loc_market" in neighbors

    def test_get_neighbors_unknown_entity(self, vault_root: Path) -> None:
        """Unknown entity returns empty set."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        assert graph.get_neighbors("nonexistent") == set()

    def test_get_neighbors_by_type(self, vault_root: Path) -> None:
        """Type-filtered neighbor query returns only matching types."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        location_neighbors = graph.get_neighbors_by_type(
            "npc_marcus", node_type="location", depth=2
        )
        assert "loc_tavern" in location_neighbors
        assert "loc_market" in location_neighbors
        assert "fac_guild" not in location_neighbors

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        """Loading an empty directory returns 0 and produces empty graph."""
        graph = VaultGraph()
        count = graph.load_from_vault(tmp_path)
        assert count == 0
        assert len(graph.get_all_node_ids()) == 0

    def test_load_skips_gm_only_pages(self, tmp_path: Path) -> None:
        npcs = tmp_path / "npcs"
        npcs.mkdir()
        (npcs / "npc_secret.md").write_text(
            "---\nid: npc_secret\ntype: npc\nname: Secret\nvisibility: gm_only\n---\n\nHidden.",
            encoding="utf-8",
        )

        graph = VaultGraph()
        count = graph.load_from_vault(tmp_path)

        assert count == 0
        assert "npc_secret" not in graph.get_all_node_ids()

    def test_load_nonexistent_directory(self) -> None:
        """Loading a nonexistent directory returns 0."""
        graph = VaultGraph()
        count = graph.load_from_vault(Path("/nonexistent"))
        assert count == 0

    def test_node_attributes(self, vault_root: Path) -> None:
        """Nodes have type and name attributes."""
        graph = VaultGraph()
        graph.load_from_vault(vault_root)
        assert graph.graph.nodes["npc_marcus"]["type"] == "npc"
        assert graph.graph.nodes["npc_marcus"]["name"] == "Marcus"
        assert graph.graph.nodes["loc_tavern"]["type"] == "location"


class TestGraphCache:
    def test_warm_and_get(self, vault_root: Path) -> None:
        """warm_vault_graph loads and caches the graph."""
        reset_vault_graph_cache()
        from sagasmith.memory.graph import get_vault_graph

        # Before warming, graph is empty
        g = get_vault_graph()
        assert len(g.get_all_node_ids()) == 0

        # Warm the cache
        warm_vault_graph(vault_root)
        g2 = get_vault_graph()
        assert len(g2.get_all_node_ids()) >= 7

    def test_reset_cache(self, vault_root: Path) -> None:
        """reset clears the cached graph."""
        warm_vault_graph(vault_root)
        reset_vault_graph_cache()
        from sagasmith.memory.graph import get_vault_graph

        g = get_vault_graph()
        assert len(g.get_all_node_ids()) == 0
