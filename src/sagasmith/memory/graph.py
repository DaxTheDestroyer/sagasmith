"""NetworkX graph loader and neighbor query for vault pages.

Builds a directed graph from wikilinks and frontmatter relationship fields
in the vault markdown files. Supports N-hop neighbor queries for MemoryPacket
retrieval.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

_WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


Frontmatter = dict[str, Any]


class VaultGraph:
    """Manages a NetworkX DiGraph built from vault page content.

    Nodes are vault page IDs. Edges come from:
    - Wikilinks ``[[page_id]]`` in body text
    - Frontmatter relationship fields:
      - Location: ``connects_to``
      - Faction: ``known_members``
      - Quest: ``related_entities``, ``callbacks``
      - Callback: ``related_quest``
      - Item: ``held_by``, ``given_by``
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph[str] = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph[str]:
        """The underlying NetworkX graph (read-only access)."""
        return self._graph

    def load_from_vault(self, vault_root: Path) -> int:
        """Scan all .md files under vault_root and build the graph.

        Returns the number of pages loaded as nodes.
        """
        self._graph.clear()
        if not vault_root.exists():
            return 0

        pages: list[tuple[str, str, Frontmatter]] = []
        for md_file in vault_root.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                fm, body = _parse_frontmatter_body(text)
                page_id = fm.get("id", "")
                if not isinstance(page_id, str) or not page_id:
                    continue
                if fm.get("visibility") == "gm_only":
                    continue
                pages.append((page_id, body, fm))
                self._graph.add_node(
                    page_id, type=fm.get("type", "unknown"), name=fm.get("name", "")
                )
            except Exception:
                continue

        for page_id, body, fm in pages:
            self._add_edges(page_id, body, fm)

        return len(pages)

    def get_neighbors(self, entity_id: str, *, depth: int = 1) -> set[str]:
        """Return IDs of nodes within *depth* hops of *entity_id*.

        Traverses both incoming and outgoing edges (undirected BFS over the
        directed graph) so that relationships in either direction are found.
        """
        if entity_id not in self._graph:
            return set()
        visited: set[str] = set()
        frontier = {entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for neighbor in self._graph.successors(node):
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                for neighbor in self._graph.predecessors(node):
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
            visited.update(frontier)
            frontier = next_frontier
        visited.update(frontier)
        visited.discard(entity_id)
        return visited

    def get_neighbors_by_type(self, entity_id: str, *, node_type: str, depth: int = 1) -> set[str]:
        """Return neighbor IDs filtered to a specific node type."""
        all_neighbors = self.get_neighbors(entity_id, depth=depth)
        return {
            nid for nid in all_neighbors if self._graph.nodes.get(nid, {}).get("type") == node_type
        }

    def get_all_node_ids(self) -> list[str]:
        """Return all node IDs in the graph."""
        return list(self._graph.nodes)

    def update_page(self, page_id: str, body: str, frontmatter: Frontmatter) -> None:
        """Add or update a single page in the graph (node + edges).

        Used for incremental graph updates during turn-close without a full
        vault rescan.
        """
        if not page_id:
            return
        self._graph.add_node(
            page_id,
            type=frontmatter.get("type", "unknown"),
            name=frontmatter.get("name", ""),
        )
        self._add_edges(page_id, body, frontmatter)

    def _add_edges(self, page_id: str, body: str, fm: Frontmatter) -> None:
        """Add edges for a single page based on its frontmatter fields and body wikilinks."""
        # Wikilinks in body
        for link in _WIKILINK_PATTERN.findall(body):
            target = link.strip()
            if target and target != page_id:
                self._graph.add_edge(page_id, target, relation="wikilink")

        page_type = fm.get("type", "")

        # Location: connects_to
        if page_type == "location":
            for target_id in fm.get("connects_to", []):
                if isinstance(target_id, str) and target_id != page_id:
                    self._graph.add_edge(page_id, target_id, relation="connects_to")

        # Faction: known_members (faction -> NPC)
        if page_type == "faction":
            for member_id in fm.get("known_members", []):
                if isinstance(member_id, str) and member_id != page_id:
                    self._graph.add_edge(page_id, member_id, relation="known_member")

        # Quest: related_entities
        if page_type == "quest":
            for rel_id in fm.get("related_entities", []):
                if isinstance(rel_id, str) and rel_id != page_id:
                    self._graph.add_edge(page_id, rel_id, relation="related_entity")
            for cb_id in fm.get("callbacks", []):
                if isinstance(cb_id, str) and cb_id != page_id:
                    self._graph.add_edge(page_id, cb_id, relation="callback")

        # Callback: related_quest
        if page_type == "callback":
            quest_id = fm.get("related_quest")
            if isinstance(quest_id, str) and quest_id and quest_id != page_id:
                self._graph.add_edge(page_id, quest_id, relation="related_quest")

        # Item: held_by, given_by
        if page_type == "item":
            for field in ("held_by", "given_by"):
                val = fm.get(field)
                if isinstance(val, str) and val and val != page_id:
                    self._graph.add_edge(page_id, val, relation=field)

        # NPC: factions (NPC -> faction)
        if page_type == "npc":
            for fac_id in fm.get("factions", []):
                if isinstance(fac_id, str) and fac_id != page_id:
                    self._graph.add_edge(page_id, fac_id, relation="faction")
            loc_id = fm.get("location_current")
            if isinstance(loc_id, str) and loc_id and loc_id != page_id:
                self._graph.add_edge(page_id, loc_id, relation="location_current")


def _parse_frontmatter_body(text: str) -> tuple[Frontmatter, str]:
    """Parse YAML frontmatter and return (frontmatter_dict, body)."""
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            try:
                loaded = yaml.safe_load(parts[1]) or {}
                fm = {str(key): value for key, value in loaded.items()} if isinstance(loaded, dict) else {}
            except yaml.YAMLError:
                fm = {}
            return fm, parts[2].strip()
    return {}, text.strip()


# ---------------------------------------------------------------------------
# Module-level singleton cache
# ---------------------------------------------------------------------------

_vault_graph: VaultGraph | None = None


def get_vault_graph() -> VaultGraph:
    """Return the cached VaultGraph, creating an empty one if needed."""
    global _vault_graph
    if _vault_graph is None:
        _vault_graph = VaultGraph()
    return _vault_graph


def warm_vault_graph(vault_root: Path) -> VaultGraph:
    """Load or reload the vault graph from disk and cache it."""
    global _vault_graph
    _vault_graph = VaultGraph()
    _vault_graph.load_from_vault(vault_root)
    return _vault_graph


def reset_vault_graph_cache() -> None:
    """Clear the cached vault graph (for testing)."""
    global _vault_graph
    _vault_graph = None
