"""Retcon Repair Module: rebuild derived layers from canonical sources.

Owns the repair ordering after a retcon status flip has been committed:
resolver refresh, graph-cache warm, FTS5 rebuild, player-vault projection.

GraphRuntime remains the Adapter for checkpoint rewind and the audited
status flip (RetconService.confirm). This Module owns everything after.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from sagasmith.vault import VaultService


@dataclass(frozen=True)
class RepairResult:
    fts5_pages: int
    graph_pages: int
    player_projection_synced: bool
    skipped_reason: str | None


class RetconRepairError(Exception):
    """Derived-layer repair failed after canonical status was committed.

    Distinct from RetconBlockedError, which signals a pre-commit veto.
    The status flip succeeded; repair can be retried independently.
    """

    def __init__(
        self, stage: Literal["graph", "fts5", "vault_projection"], cause: Exception
    ) -> None:
        super().__init__(f"retcon repair failed at stage '{stage}': {cause}")
        self.stage = stage
        self.__cause__ = cause


def repair_from_canonical(
    *,
    db_conn: sqlite3.Connection,
    vault_service: VaultService | None,
) -> RepairResult:
    """Rebuild all derived layers from canonical vault sources.

    Call this after RetconService.confirm has committed and the checkpoint
    rewind has been applied. Returns counts for CLI/logging; raises
    RetconRepairError on the first failing stage.
    """
    if vault_service is None:
        return RepairResult(
            fts5_pages=0,
            graph_pages=0,
            player_projection_synced=False,
            skipped_reason="no_vault_service",
        )

    from sagasmith.memory.fts5 import FTS5Index
    from sagasmith.memory.graph import reset_vault_graph_cache, warm_vault_graph

    master_path = vault_service.master_path

    try:
        vault_service.resolver.refresh()
        reset_vault_graph_cache()
        graph = warm_vault_graph(master_path)
        graph_pages = len(graph.get_all_node_ids())
    except Exception as exc:
        raise RetconRepairError("graph", exc) from exc

    try:
        fts5_pages = FTS5Index(db_conn).rebuild_all(master_path)
    except Exception as exc:
        raise RetconRepairError("fts5", exc) from exc

    try:
        vault_service.sync()
    except Exception as exc:
        raise RetconRepairError("vault_projection", exc) from exc

    return RepairResult(
        fts5_pages=fts5_pages,
        graph_pages=graph_pages,
        player_projection_synced=True,
        skipped_reason=None,
    )
