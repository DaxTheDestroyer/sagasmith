"""Turn Plan: assemble the Archivist's work for one turn.

Consumes state and injected collaborators; produces a TurnPlan value.
Never performs SQLite or vault writes — that is the runtime's turn_close
responsibility (ADR-0001 lines 113-116).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sagasmith.providers.client import LLMClient
from sagasmith.schemas.deltas import CanonConflict
from sagasmith.schemas.narrative import MemoryPacket
from sagasmith.vault import VaultPage, VaultService


@dataclass(frozen=True)
class TurnPlanContext:
    """Everything build_turn_plan needs. Plain mappings and injected collaborators."""

    state: Mapping[str, Any]
    vault_service: VaultService | None
    transcript_conn: sqlite3.Connection | None
    llm: LLMClient | None


@dataclass(frozen=True)
class TurnPlan:
    """Result of build_turn_plan: everything the Adapter needs to project onto state."""

    session_state: Mapping[str, Any]
    rolling_summary: Any
    pending_conflicts: Sequence[CanonConflict]
    memory_packet: MemoryPacket
    pending_vault_writes: tuple[VaultPage, ...]
    pending_narration: Sequence[str]


def build_turn_plan(context: TurnPlanContext) -> TurnPlan:
    """Produce the Archivist's turn plan from state and collaborators.

    Composes entity resolution, vault-page upsert, visibility promotion,
    rolling summary update, canon conflict detection, and memory packet
    assembly into a single explicit TurnPlan value.
    """
    raise NotImplementedError
