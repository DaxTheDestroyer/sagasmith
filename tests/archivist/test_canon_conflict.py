"""Tests for canon-conflict-detection stub."""

from __future__ import annotations

import logging

from sagasmith.agents.archivist.skills.canon_conflict_detection.logic import detect_conflicts
from sagasmith.vault.page import NpcFrontmatter, VaultPage


def test_detect_conflicts_stub_returns_empty_and_logs_warning(caplog: object) -> None:
    page = VaultPage(
        NpcFrontmatter(
            id="npc_marcus",
            type="npc",
            name="Marcus",
            aliases=[],
            visibility="player_known",
            species="human",
            role="innkeeper",
            status="alive",
            disposition_to_pc="neutral",
        )
    )

    with caplog.at_level(logging.WARNING, logger="sagasmith.archivist.canon_conflict"):  # type: ignore[attr-defined]
        conflicts = detect_conflicts("Marcus is actually a dragon", [page])

    assert conflicts == []
    assert "canon_conflict_stub" in caplog.text  # type: ignore[attr-defined]
