"""FTS5 full-text search index over vault page bodies.

Provides incremental index updates on vault writes and keyword-based
search for MemoryPacket retrieval.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_FTS_TABLE = "vault_fts"


class FTS5Index:
    """FTS5-backed vault page search index.

    Uses a dedicated FTS5 virtual table stored alongside the campaign
    database. Each row maps a vault_path to its body text for keyword
    retrieval.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE} "
            "USING fts5(vault_path UNINDEXED, content)"
        )

    def index_page(self, vault_path: str, content: str) -> None:
        """Upsert a single vault page into the FTS5 index.

        Deletes any existing row for this path, then inserts the new content.
        This is safe for both create and update scenarios.
        """
        self._conn.execute(
            f"DELETE FROM {_FTS_TABLE} WHERE vault_path = ?",
            (vault_path,),
        )
        self._conn.execute(
            f"INSERT INTO {_FTS_TABLE} (vault_path, content) VALUES (?, ?)",
            (vault_path, content),
        )
        self._conn.commit()

    def remove_page(self, vault_path: str) -> None:
        """Remove a vault page from the FTS5 index."""
        self._conn.execute(
            f"DELETE FROM {_FTS_TABLE} WHERE vault_path = ?",
            (vault_path,),
        )
        self._conn.commit()

    def rebuild_all(self, vault_root: Path) -> int:
        """Scan all .md files under vault_root and rebuild the FTS5 index.

        Strips YAML frontmatter before indexing the body content. Skips
        gm_only pages per the threat model (T-07-10): only player_known
        and foreshadowed pages are indexed.

        Returns the number of pages indexed.
        """
        self._conn.execute(f"DELETE FROM {_FTS_TABLE}")
        count = 0
        if not vault_root.exists():
            self._conn.commit()
            return count
        for md_file in vault_root.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                body = _extract_body(text)
                if not body:
                    continue
                visibility = _extract_visibility(text)
                if visibility == "gm_only":
                    continue
                rel_path = str(md_file.relative_to(vault_root)).replace("\\", "/")
                self._conn.execute(
                    f"INSERT INTO {_FTS_TABLE} (vault_path, content) VALUES (?, ?)",
                    (rel_path, body),
                )
                count += 1
            except Exception:
                continue
        self._conn.commit()
        return count

    def query(self, search_term: str, *, limit: int = 5) -> list[tuple[str, float]]:
        """Search the FTS5 index for vault pages matching search_term.

        Returns a list of (vault_path, rank) tuples ordered by relevance.
        Lower rank values indicate better matches (FTS5 convention).
        Returns empty list if no matches.
        """
        if not search_term.strip():
            return []
        try:
            rows = self._conn.execute(
                f"SELECT vault_path, rank FROM {_FTS_TABLE} "
                "WHERE vault_fts MATCH ? ORDER BY rank LIMIT ?",
                (search_term, limit),
            ).fetchall()
            return [(row[0], row[1]) for row in rows]
        except sqlite3.OperationalError:
            return []


def get_fts5_index(conn: sqlite3.Connection) -> FTS5Index:
    """Factory: return an FTS5Index backed by the given connection."""
    return FTS5Index(conn)


def _extract_body(text: str) -> str:
    """Strip YAML frontmatter delimited by --- and return the body."""
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def _extract_visibility(text: str) -> str | None:
    """Extract the visibility field from YAML frontmatter without a full YAML parser.

    Returns the visibility value or None if not found.
    """
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) < 2:
        return None
    frontmatter = parts[1]
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("visibility:"):
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            return value
    return None
