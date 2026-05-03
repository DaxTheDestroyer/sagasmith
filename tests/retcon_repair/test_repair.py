"""Tests for the Retcon Repair Module Interface.

All tests call repair_from_canonical directly — no GraphRuntime or Textual.
Collaborators: real VaultService on tmp_path, :memory: sqlite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

import sagasmith.vault.paths as vp
from sagasmith.memory.fts5 import FTS5Index
from sagasmith.memory.graph import get_vault_graph, reset_vault_graph_cache
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.retcon_repair import RepairResult, RetconRepairError, repair_from_canonical
from sagasmith.vault import VaultService, VaultSyncError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PAGE_VISIBLE = (
    "---\nid: lore_seen\ntype: lore\nname: Seen\nvisibility: player_known\n---\n\nVisible body.\n"
)
_PAGE_GM_ONLY = (
    "---\nid: lore_secret\ntype: lore\nname: Secret\nvisibility: gm_only\n---\n\nHidden.\n"
)


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VaultService:
    monkeypatch.setattr(vp, "DEFAULT_MASTER_OPTS", tmp_path / ".ttrpg" / "vault")
    svc = VaultService("cmp_repair", tmp_path / "player_vault")
    svc.ensure_master_path()
    return svc


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(c)
    return c


def _write_master(vault: VaultService, filename: str, content: str) -> None:
    (vault.master_path / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rebuild_returns_counts_and_syncs_player_projection(
    vault: VaultService, conn: sqlite3.Connection, tmp_path: Path
) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)
    _write_master(
        vault, "page_b.md", _PAGE_VISIBLE.replace("lore_seen", "lore_b").replace("Seen", "B")
    )
    _write_master(
        vault, "page_c.md", _PAGE_VISIBLE.replace("lore_seen", "lore_c").replace("Seen", "C")
    )
    _write_master(vault, "secret.md", _PAGE_GM_ONLY)

    result = repair_from_canonical(db_conn=conn, vault_service=vault)

    assert result.fts5_pages == 3  # gm_only excluded from FTS5 index
    assert result.graph_pages >= 3
    assert result.player_projection_synced is True
    assert result.skipped_reason is None
    player_files = list(vault.player_vault_root.rglob("*.md"))
    names = {f.name for f in player_files}
    assert "secret.md" not in names  # gm_only excluded from player vault
    assert "page_a.md" in names


def test_returns_skipped_reason_when_vault_service_is_none(
    conn: sqlite3.Connection,
) -> None:
    result = repair_from_canonical(db_conn=conn, vault_service=None)

    assert result == RepairResult(
        fts5_pages=0,
        graph_pages=0,
        player_projection_synced=False,
        skipped_reason="no_vault_service",
    )


def test_idempotent_when_called_twice(vault: VaultService, conn: sqlite3.Connection) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)

    first = repair_from_canonical(db_conn=conn, vault_service=vault)
    second = repair_from_canonical(db_conn=conn, vault_service=vault)

    assert first.fts5_pages == second.fts5_pages
    assert conn.execute("SELECT COUNT(*) FROM vault_fts").fetchone()[0] == first.fts5_pages


def test_fts5_pages_are_queryable_after_repair(
    vault: VaultService, conn: sqlite3.Connection
) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)

    repair_from_canonical(db_conn=conn, vault_service=vault)

    hits = FTS5Index(conn).query("Visible")
    assert len(hits) >= 1


def test_graph_cache_is_warmed_after_repair(vault: VaultService, conn: sqlite3.Connection) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)
    reset_vault_graph_cache()

    repair_from_canonical(db_conn=conn, vault_service=vault)

    assert len(get_vault_graph().get_all_node_ids()) >= 1


def test_fts5_rebuild_failure_raises_repair_error_with_stage(
    vault: VaultService,
) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)
    closed = sqlite3.connect(":memory:")
    closed.close()

    with pytest.raises(RetconRepairError) as exc_info:
        repair_from_canonical(db_conn=closed, vault_service=vault)

    assert exc_info.value.stage == "fts5"
    assert exc_info.value.__cause__ is not None


def test_player_projection_failure_raises_repair_error_with_stage(
    vault: VaultService, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)

    def _fail_sync() -> None:
        raise VaultSyncError("disk full")

    monkeypatch.setattr(vault, "sync", _fail_sync)

    with pytest.raises(RetconRepairError) as exc_info:
        repair_from_canonical(db_conn=conn, vault_service=vault)

    assert exc_info.value.stage == "vault_projection"
    assert isinstance(exc_info.value.__cause__, VaultSyncError)


def test_repair_does_not_call_rebuild_indices(
    vault: VaultService, conn: sqlite3.Connection
) -> None:
    """repair_from_canonical must not delegate to VaultService.rebuild_indices.

    That method calls FTS5 + graph internally, which would double the work.
    This test encodes the fix for the duplicate-rebuild bug in the old
    GraphRuntime.confirm_retcon.
    """
    _write_master(vault, "page_a.md", _PAGE_VISIBLE)

    with patch.object(vault, "rebuild_indices", wraps=vault.rebuild_indices) as spy:
        repair_from_canonical(db_conn=conn, vault_service=vault)

    spy.assert_not_called()
