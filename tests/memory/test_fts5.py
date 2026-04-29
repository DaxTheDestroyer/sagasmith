"""Unit tests for FTS5 full-text search index over vault pages."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sagasmith.memory.fts5 import (
    FTS5Index,
    _extract_body,  # pyright: ignore[reportPrivateUsage]
    _extract_visibility,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with FTS5 support."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA journal_mode=WAL")
    return c


@pytest.fixture
def fts(conn: sqlite3.Connection) -> FTS5Index:
    """FTS5Index backed by in-memory connection."""
    return FTS5Index(conn)


class TestFTS5Index:
    def test_create_table(self, fts: FTS5Index) -> None:
        """Virtual table is created without error."""
        tables = fts._conn.execute(  # pyright: ignore[reportPrivateUsage]
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_fts'"
        ).fetchall()
        assert len(tables) == 1

    def test_index_and_query(self, fts: FTS5Index) -> None:
        """Indexed page can be found by keyword query."""
        fts.index_page("npcs/npc_marcus.md", "Marcus runs the Bent Copper tavern.")
        fts.index_page("locations/loc_tavern.md", "The Bent Copper is a low-ceilinged tavern.")
        fts.index_page("npcs/npc_sera.md", "Sera is a worried wife looking for her husband.")

        results = fts.query("tavern")
        paths = [r[0] for r in results]
        assert "npcs/npc_marcus.md" in paths
        assert "locations/loc_tavern.md" in paths
        assert "npcs/npc_sera.md" not in paths

    def test_query_no_match(self, fts: FTS5Index) -> None:
        """Query with no matches returns empty list."""
        fts.index_page("npcs/npc_marcus.md", "Marcus runs the tavern.")
        results = fts.query("dragonfire")
        assert results == []

    def test_query_empty_term(self, fts: FTS5Index) -> None:
        """Empty query term returns empty list."""
        fts.index_page("npcs/npc_marcus.md", "Marcus runs the tavern.")
        results = fts.query("")
        assert results == []

    def test_upsert_replaces_content(self, fts: FTS5Index) -> None:
        """Re-indexing the same path replaces old content."""
        fts.index_page("npcs/npc_marcus.md", "Marcus runs the tavern.")
        fts.index_page("npcs/npc_marcus.md", "Marcus is now a blacksmith.")

        results_old = fts.query("tavern")
        assert len(results_old) == 0

        results_new = fts.query("blacksmith")
        assert len(results_new) == 1
        assert results_new[0][0] == "npcs/npc_marcus.md"

    def test_remove_page(self, fts: FTS5Index) -> None:
        """Removed page no longer appears in results."""
        fts.index_page("npcs/npc_marcus.md", "Marcus runs the tavern.")
        fts.remove_page("npcs/npc_marcus.md")

        results = fts.query("Marcus")
        assert len(results) == 0

    def test_limit_parameter(self, fts: FTS5Index) -> None:
        """Limit parameter restricts result count."""
        for i in range(10):
            fts.index_page(f"npcs/npc_{i}.md", f"Entity {i} is a warrior.")
        results = fts.query("warrior", limit=3)
        assert len(results) == 3

    def test_rebuild_all(self, fts: FTS5Index, tmp_path: Path) -> None:
        """Rebuild scans all .md files and populates the index."""
        # Create vault structure
        npcs_dir = tmp_path / "npcs"
        npcs_dir.mkdir()
        locs_dir = tmp_path / "locations"
        locs_dir.mkdir()

        (npcs_dir / "npc_marcus.md").write_text(
            "---\nid: npc_marcus\ntype: npc\nname: Marcus\nvisibility: player_known\n---\n\nMarcus the innkeeper.",
            encoding="utf-8",
        )
        (locs_dir / "loc_tavern.md").write_text(
            "---\nid: loc_tavern\ntype: location\nname: Tavern\nvisibility: player_known\n---\n\nA cozy tavern.",
            encoding="utf-8",
        )
        # gm_only page should be skipped
        (npcs_dir / "npc_secret.md").write_text(
            "---\nid: npc_secret\ntype: npc\nname: Secret Agent\nvisibility: gm_only\n---\n\nHidden agent.",
            encoding="utf-8",
        )

        count = fts.rebuild_all(tmp_path)
        assert count == 2

        results = fts.query("innkeeper")
        assert len(results) == 1
        assert "npc_marcus" in results[0][0]

        # gm_only page not indexed
        results_secret = fts.query("Hidden agent")
        assert len(results_secret) == 0

    def test_rebuild_all_empty_dir(self, fts: FTS5Index, tmp_path: Path) -> None:
        """Rebuild on empty directory returns 0."""
        count = fts.rebuild_all(tmp_path)
        assert count == 0

    def test_rebuild_all_nonexistent_dir(self, fts: FTS5Index) -> None:
        """Rebuild on nonexistent directory returns 0."""
        count = fts.rebuild_all(Path("/nonexistent/path"))
        assert count == 0

    def test_rebuild_all_clears_old_data(self, fts: FTS5Index, tmp_path: Path) -> None:
        """Rebuild replaces all existing data."""
        fts.index_page("old/path.md", "Old content that should be gone.")
        assert len(fts.query("Old content")) == 1

        npcs_dir = tmp_path / "npcs"
        npcs_dir.mkdir()
        (npcs_dir / "npc_new.md").write_text(
            "---\nid: npc_new\ntype: npc\nname: New\nvisibility: player_known\n---\n\nNew entity.",
            encoding="utf-8",
        )
        fts.rebuild_all(tmp_path)

        assert len(fts.query("Old content")) == 0
        assert len(fts.query("entity")) == 1


class TestHelpers:
    def test_extract_body_with_frontmatter(self) -> None:
        text = "---\nid: test\n---\n\nBody content here."
        assert _extract_body(text) == "Body content here."

    def test_extract_body_no_frontmatter(self) -> None:
        text = "Just plain text."
        assert _extract_body(text) == "Just plain text."

    def test_extract_visibility_found(self) -> None:
        text = "---\nid: test\nvisibility: player_known\n---\n\nBody."
        assert _extract_visibility(text) == "player_known"

    def test_extract_visibility_gm_only(self) -> None:
        text = "---\nid: test\nvisibility: gm_only\n---\n\nBody."
        assert _extract_visibility(text) == "gm_only"

    def test_extract_visibility_not_found(self) -> None:
        text = "---\nid: test\n---\n\nBody."
        assert _extract_visibility(text) is None

    def test_extract_visibility_no_frontmatter(self) -> None:
        text = "No frontmatter here."
        assert _extract_visibility(text) is None

    def test_extract_visibility_quoted(self) -> None:
        text = '---\nid: test\nvisibility: "foreshadowed"\n---\n\nBody.'
        assert _extract_visibility(text) == "foreshadowed"
