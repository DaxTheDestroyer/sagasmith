"""Tests for resume session numbering and vault warning status."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from sagasmith.app.campaign import init_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.repositories import TurnRecordRepository
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.tui.runtime import build_app
from sagasmith.tui.state import StatusSnapshot
from sagasmith.tui.widgets.status_panel import format_status_snapshot


def test_build_app_increments_session_number_on_resume(tmp_path: Path) -> None:
    root = tmp_path / "rivermouth"
    manifest = init_campaign(name="Rivermouth", root=root, provider="fake")
    conn = open_campaign_db(root / "campaign.sqlite")
    try:
        TurnRecordRepository(conn).upsert(
            TurnRecord(
                turn_id="turn_000001",
                campaign_id=manifest.campaign_id,
                session_id="session_002",
                status="complete",
                started_at="2026-04-29T00:00:00Z",
                completed_at="2026-04-29T00:01:00Z",
                schema_version=1,
            )
        )
        conn.commit()
    finally:
        conn.close()

    app = build_app(root, build_graph_runtime=False)

    assert app.current_session_id == "session_003"
    build_state = cast(Callable[[str, dict[str, object]], dict[str, Any]], getattr(app, "_build_play_state"))
    session_state = cast(dict[str, Any], build_state("look", {})["session_state"])
    assert session_state["session_number"] == 3
    app.on_unmount()


def test_status_snapshot_renders_vault_sync_warning() -> None:
    rendered = format_status_snapshot(
        StatusSnapshot(vault_sync_warning="Player vault sync failed; run ttrpg vault sync.")
    )

    assert "VAULT SYNC WARNING" in rendered
    assert "ttrpg vault sync" in rendered
