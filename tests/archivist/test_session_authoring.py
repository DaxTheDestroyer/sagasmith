"""Tests for session-page-authoring skill."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sagasmith.agents.archivist.skills.session_page_authoring.logic import author_session
from sagasmith.vault import VaultService


@pytest.fixture
def vault_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VaultService:
    import sagasmith.vault.paths as vp

    monkeypatch.setattr(vp, "DEFAULT_MASTER_OPTS", tmp_path / ".ttrpg" / "vault")
    service = VaultService(campaign_id="test_campaign", player_vault_root=tmp_path / "player")
    service.ensure_master_path()
    return service


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE turn_records (turn_id TEXT, campaign_id TEXT, session_id TEXT, status TEXT, started_at TEXT, completed_at TEXT, schema_version INTEGER, sync_warning TEXT)"
    )
    conn.execute(
        "CREATE TABLE transcript_entries (turn_id TEXT, kind TEXT, content TEXT, sequence INTEGER, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE roll_logs (roll_id TEXT, turn_id TEXT, seed TEXT, die TEXT, natural INTEGER, modifier INTEGER, total INTEGER, dc INTEGER, timestamp TEXT)"
    )
    conn.execute(
        "INSERT INTO turn_records VALUES ('turn_1', 'test_campaign', 'session_001', 'complete', '', '', 1, NULL)"
    )
    conn.execute(
        "INSERT INTO transcript_entries VALUES ('turn_1', 'scene_brief', 'Beat: Meet [[npc_marcus|Marcus]] at [[loc_tavern|the tavern]]', 0, '2026-04-29T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO transcript_entries VALUES ('turn_1', 'narration_final', 'Marcus offered a room and Sera asked for help.', 1, '2026-04-29T00:00:01Z')"
    )
    conn.execute(
        "INSERT INTO roll_logs VALUES ('roll_1', 'turn_1', 'seed', 'd20', 12, 4, 16, 14, '2026-04-29T00:00:02Z')"
    )
    return conn


def test_author_session_writes_frontmatter_beats_and_roll_table(
    vault_service: VaultService,
) -> None:
    path = author_session(
        session_number=1,
        campaign_id="test_campaign",
        db_conn=_conn(),
        vault_service=vault_service,
    )

    assert path == "sessions/session_001.md"
    text = (vault_service.master_path / path).read_text(encoding="utf-8")
    assert "id: session_001" in text
    assert "type: session" in text
    assert "visibility: player_known" in text
    assert "## Beats" in text
    assert "Meet [[npc_marcus|Marcus]]" in text
    assert "## Rolls" in text
    assert "| roll_1 | d20 | 12 | +4 | 16 | 14 |" in text
