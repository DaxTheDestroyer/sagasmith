"""SqliteSaver integration helpers. All checkpoint-ref writing is owned by runtime.py."""

from __future__ import annotations

import sqlite3
from enum import StrEnum

from langgraph.checkpoint.sqlite import SqliteSaver


class CheckpointKind(StrEnum):
    PRE_NARRATION = "pre_narration"
    FINAL = "final"


def build_checkpointer(conn: sqlite3.Connection) -> SqliteSaver:
    """Construct a SqliteSaver bound to the caller's connection.

    SqliteSaver creates its own tables on first use. These are separate from
    SagaSmith's `checkpoint_refs` metadata table (see migration 0001). The
    Plan 04-02 Task 1 spike test verifies non-collision at CI time.
    """
    return SqliteSaver(conn=conn)


def extract_checkpoint_id(snapshot) -> str | None:
    """Pull the opaque LangGraph checkpoint_id from a StateSnapshot.

    Proven accessible by Task 1 spike. If LangGraph ever changes the shape,
    spike test fails first and this helper is the single point of adaptation.
    """
    cfg = getattr(snapshot, "config", None) or {}
    inner = cfg.get("configurable", {}) if isinstance(cfg, dict) else {}
    return inner.get("checkpoint_id")
