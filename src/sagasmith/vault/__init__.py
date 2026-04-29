"""Vault service: deterministic storage layer for campaign canon.

Provides path resolution, atomic page writes with post-write validation,
entity resolution by slug/alias, player-vault projection sync, and the
top-level service object injected into agent services.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .page import (
    NPC_PAGE_TYPES,
    BaseVaultFrontmatter,
    CallbackFrontmatter,
    FactionFrontmatter,
    ItemFrontmatter,
    LocationFrontmatter,
    LoreFrontmatter,
    NpcFrontmatter,
    QuestFrontmatter,
    SessionFrontmatter,
    VaultPage,
)
from .paths import ensure_player_vault_path, get_master_vault_path
from .resolver import EntityResolver
from .writer import atomic_write

__all__ = [
    "NPC_PAGE_TYPES",
    "BaseVaultFrontmatter",
    "EntityResolver",
    "VaultPage",
    "VaultService",
    "VaultSyncError",
    "atomic_write",
    "ensure_player_vault_path",
    "get_master_vault_path",
]


class VaultSyncError(RuntimeError):
    """Raised when the player-vault projection cannot be completed safely."""


class VaultService:
    """Owns vault roots and entity resolution.

    The Archivist uses this service to write pages, resolve entities, and
    sync the player vault projection.
    """

    def __init__(self, campaign_id: str, player_vault_root: Path):
        self.master_path = get_master_vault_path(campaign_id)
        self.player_vault_root = player_vault_root
        self._resolver = EntityResolver(self.master_path)

    @property
    def resolver(self) -> EntityResolver:
        """Entity resolution engine for the master vault."""
        return self._resolver

    def write_page(self, page: VaultPage, relative_path: Path, *, is_master: bool = True) -> Path:
        """Atomically write a vault page to the appropriate vault.

        Args:
            page: The vault page to write.
            relative_path: Path relative to vault root (e.g. 'npc/orym_the_humble.md').
            is_master: If True, write to master vault; else to player vault.

        Returns:
            The absolute path of the written file.
        """
        base = self.master_path if is_master else self.player_vault_root
        target = base / relative_path
        atomic_write(page, target)
        return target

    def ensure_master_path(self) -> None:
        """Ensure master vault directory exists."""
        self.master_path.mkdir(parents=True, exist_ok=True)

    def ensure_player_vault(self) -> None:
        """Ensure player vault directory exists."""
        self.player_vault_root.mkdir(parents=True, exist_ok=True)

    def sync(self) -> None:
        """Project master vault to player vault with visibility filtering.

        For each page in master vault:
        - gm_only: skip (not written to player vault)
        - foreshadowed: write stub with minimal frontmatter, empty body
        - player_known: write full page with GM-only fields stripped from
          frontmatter and body (comments between <!-- gm: ... --> removed).

        Atomic writes per file; failures raise :class:`VaultSyncError`.
        """
        try:
            self.ensure_player_vault()
            projected_pages = self._project_visible_pages()
            self._clear_player_markdown_projection()
            for rel, page in projected_pages:
                atomic_write(page, self.player_vault_root / rel)
            self._regenerate_index(projected_pages)
            self._regenerate_log(projected_pages)
        except VaultSyncError:
            raise
        except OSError as exc:
            raise VaultSyncError(f"player vault sync failed: {exc}") from exc
        except ValueError as exc:
            raise VaultSyncError(f"player vault sync failed: {exc}") from exc

    def rebuild_indices(self, conn: object | None = None) -> dict[str, int]:
        """Rebuild derived read layers from the master vault.

        Returns counts for CLI reporting. FTS5 is rebuilt when a SQLite
        connection is supplied; the NetworkX graph cache is always warmed from
        the master vault. LanceDB remains future-scoped for this MVP slice.
        """
        counts: dict[str, int] = {"graph_pages": 0, "fts5_pages": 0}
        self.resolver.refresh()
        from sagasmith.memory.graph import warm_vault_graph

        graph = warm_vault_graph(self.master_path)
        counts["graph_pages"] = len(graph.get_all_node_ids())
        if conn is not None:
            import sqlite3

            if isinstance(conn, sqlite3.Connection):
                from sagasmith.memory.fts5 import FTS5Index

                counts["fts5_pages"] = FTS5Index(conn).rebuild_all(self.master_path)
        return counts

    def _project_visible_pages(self) -> list[tuple[Path, VaultPage]]:
        projected: list[tuple[Path, VaultPage]] = []
        for md_file in sorted(self.master_path.rglob("*.md")):
            rel = md_file.relative_to(self.master_path)
            if rel.parts and rel.parts[0] == "meta":
                continue
            page = VaultPage.load_file(md_file)
            visibility = page.frontmatter.visibility
            if visibility == "gm_only":
                continue
            if visibility == "foreshadowed":
                projected.append((rel, _foreshadowed_stub(page)))
            elif visibility == "player_known":
                projected.append((rel, _strip_player_known_page(page)))
        return projected

    def _clear_player_markdown_projection(self) -> None:
        if not self.player_vault_root.exists():
            return
        for md_file in self.player_vault_root.rglob("*.md"):
            md_file.unlink()

    def _regenerate_index(self, projected_pages: Iterable[tuple[Path, VaultPage]]) -> None:
        pages = sorted(
            projected_pages, key=lambda item: (item[1].frontmatter.type, item[1].frontmatter.name)
        )
        lines = ["# World Overview", "", "*Auto-generated from known campaign facts.*", ""]
        grouped: dict[str, list[tuple[Path, VaultPage]]] = {}
        for rel, page in pages:
            grouped.setdefault(page.frontmatter.type, []).append((rel, page))
        headings = {
            "npc": "NPCs",
            "location": "Locations",
            "faction": "Factions",
            "item": "Items",
            "quest": "Quests",
            "callback": "Callbacks",
            "session": "Sessions",
            "lore": "Lore",
        }
        for page_type, title in headings.items():
            entries = grouped.get(page_type, [])
            if not entries:
                continue
            lines.extend([f"## {title}", ""])
            for rel, page in entries:
                stem = rel.with_suffix("").as_posix()
                lines.append(f"- [[{stem}|{page.frontmatter.name}]]")
            lines.append("")
        _write_generated_page(
            self.player_vault_root / "index.md",
            "# World Overview",
            "\n".join(lines).rstrip() + "\n",
        )

    def _regenerate_log(self, projected_pages: Iterable[tuple[Path, VaultPage]]) -> None:
        pages = sorted(projected_pages, key=lambda item: item[1].frontmatter.id)
        lines = ["# Campaign Log", "", "*Auto-generated from visible vault pages.*", ""]
        for _rel, page in pages:
            lines.append(f"## visible | {page.frontmatter.id} — {page.frontmatter.name}")
        _write_generated_page(
            self.player_vault_root / "log.md",
            "# Campaign Log",
            "\n".join(lines).rstrip() + "\n",
        )


def _strip_gm_comments(body: str) -> str:
    """Remove all <!-- gm: ... --> comment blocks from body text."""
    # Regex matches <!-- gm: ... --> possibly spanning newlines (non-greedy)
    pattern = re.compile(r"<!--\s*gm:.*?-->", re.DOTALL)
    return pattern.sub("", body)


def _foreshadowed_stub(page: VaultPage) -> VaultPage:
    """Create a foreshadowed stub preserving non-GM fields but stripping any GM-only keys."""
    # Serialize original frontmatter to a mutable dict
    front_dict = page.frontmatter.model_dump(mode="json")
    # Remove any GM-only fields that must not appear in player vault
    gm_keys = {"secrets", "gm_notes"} | {k for k in front_dict if k.startswith("gm_")}
    for k in gm_keys:
        front_dict.pop(k, None)
    # Downgrade visibility
    front_dict["visibility"] = "foreshadowed"
    # Validate with the concrete frontmatter class derived from type
    cls = _frontmatter_type_for(front_dict.get("type"))
    stub_front = cls.model_validate(front_dict)
    body = "*Unknown - you have heard this name but know little more.*"
    return VaultPage(stub_front, body)


def _strip_player_known_page(page: VaultPage) -> VaultPage:
    front_dict = page.frontmatter.model_dump(mode="json")
    gm_keys = {"secrets", "gm_notes"} | {k for k in front_dict if k.startswith("gm_")}
    for key in gm_keys:
        front_dict.pop(key, None)
    clean_front = _frontmatter_type_for(front_dict.get("type")).model_validate(front_dict)
    return VaultPage(clean_front, _strip_gm_comments(page.body).strip())


def _write_generated_page(target: Path, title: str, body: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(target)
    except Exception as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise VaultSyncError(f"failed to write generated {title}: {exc}") from exc


def _frontmatter_type_for(type_name: object) -> type[BaseVaultFrontmatter]:
    mapping: dict[str, type[BaseVaultFrontmatter]] = {
        "npc": NpcFrontmatter,
        "location": LocationFrontmatter,
        "faction": FactionFrontmatter,
        "item": ItemFrontmatter,
        "quest": QuestFrontmatter,
        "callback": CallbackFrontmatter,
        "session": SessionFrontmatter,
        "lore": LoreFrontmatter,
    }
    return (
        mapping.get(type_name, BaseVaultFrontmatter)
        if isinstance(type_name, str)
        else BaseVaultFrontmatter
    )
