"""Tests for PauseCommand and LineCommand (SAFE-04, SAFE-05, SAFE-06)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.repositories import SafetyEventRepository
from sagasmith.services.safety import SafetyEventService
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand
from sagasmith.tui.widgets.narration import NarrationArea


def _make_app_with_safety(tmp_path: Path) -> tuple[SagaSmithApp, str]:
    """Create a campaign-backed SagaSmithApp with SafetyEventService bound."""
    root = tmp_path / "c"
    init_campaign(name="Safety Test", root=root, provider="fake")
    paths, m = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=m)
    # Open a persistent connection and bind safety service
    conn = open_campaign_db(paths.db, read_only=False)
    app.safety_events = SafetyEventService(conn=conn)
    registry = CommandRegistry()
    registry.register(PauseCommand())
    registry.register(LineCommand())
    app.commands = registry  # type: ignore[assignment]
    return app, m.campaign_id


def _make_app_no_safety(tmp_path: Path) -> SagaSmithApp:
    """Create a SagaSmithApp with safety_events = None."""
    root = tmp_path / "c"
    init_campaign(name="No Safety Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=manifest)
    # Explicitly leave safety_events as None
    registry = CommandRegistry()
    registry.register(PauseCommand())
    registry.register(LineCommand())
    app.commands = registry  # type: ignore[assignment]
    return app


# ---------------------------------------------------------------------------
# SAFE-04: /pause persists safety event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_persists_safety_event(tmp_path: Path) -> None:
    """SAFE-04: /pause writes a SafetyEventRecord(kind='pause') to SQLite."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    logged: list[str] = []

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "[SAFETY] Paused." in combined, f"Expected '[SAFETY] Paused.' in: {logged}"
    assert "event safety_" in combined, f"Expected 'event safety_' in: {logged}"

    # Verify DB row exists
    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].kind == "pause"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SAFE-05: /line persists safety event with topic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_line_persists_safety_event_with_topic(tmp_path: Path) -> None:
    """SAFE-05: /line graphic_violence persists a row with the correct policy_ref."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    logged: list[str] = []

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/line graphic_violence":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "Line drawn: graphic_violence" in combined, f"Expected line drawn msg; got: {logged}"

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].policy_ref == "graphic_violence"
        assert rows[0].action_taken == "redlined:graphic_violence"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_line_without_args_prints_usage(tmp_path: Path) -> None:
    """/line alone → narration says '/line requires a topic'; no DB row written."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    logged: list[str] = []

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/line":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any("/line requires a topic" in line for line in logged), f"Expected usage msg; got: {logged}"

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_line_with_multi_word_topic_joins_args(tmp_path: Path) -> None:
    """/line detailed torture scenes → topic stored as 'detailed torture scenes'."""
    app, campaign_id = _make_app_with_safety(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/line detailed torture scenes":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].policy_ref == "detailed torture scenes"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_pause_without_safety_service_does_not_crash(tmp_path: Path) -> None:
    """safety_events=None → narration says 'No campaign bound', no exception."""
    app = _make_app_no_safety(tmp_path)
    logged: list[str] = []

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any("No campaign bound" in line for line in logged), f"Expected 'No campaign bound'; got: {logged}"


@pytest.mark.asyncio
async def test_line_rejects_secret_shaped_topic(tmp_path: Path) -> None:
    """SAFE-06 + QA-04: secret-shaped topic → narration contains 'rejected', no DB row."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    # Use a sufficiently long secret-shaped topic to trigger the canary
    secret_topic = "sk-proj-supersecretkeyblablabla"
    logged: list[str] = []

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in f"/line {secret_topic}":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "rejected" in combined, f"Expected 'rejected' in: {logged}"

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 0
    finally:
        conn.close()
