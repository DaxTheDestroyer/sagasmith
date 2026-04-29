"""Structured warning stub for canon-conflict detection."""

from __future__ import annotations

import logging

from sagasmith.schemas.deltas import CanonConflict
from sagasmith.vault.page import VaultPage

LOGGER = logging.getLogger("sagasmith.archivist.canon_conflict")


def detect_conflicts(player_input: str, vault_pages: list[VaultPage]) -> list[CanonConflict]:
    """Return an empty conflict list while logging potential conflict surface.

    Phase 7 intentionally ships this as a non-blocking stub: it emits a
    structured warning for observability but does not raise or route conflict
    events until full conflict extraction is implemented.
    """

    LOGGER.warning(
        "canon_conflict_stub player_input_present=%s vault_pages=%s",
        bool(player_input.strip()),
        len(vault_pages),
    )
    return []
