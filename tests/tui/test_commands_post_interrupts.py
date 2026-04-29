"""Tests for TUI commands posting graph interrupts (Phase 4) while preserving
Phase 3 SafetyEvent writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.graph.interrupts import InterruptKind
from sagasmith.persistence.db import open_campaign_db
from sagasmith.services.safety import SafetyEventService
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import SaveCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand
from sagasmith.tui.widgets.narration import NarrationArea


def _make_app_with_safety(tmp_path: Path) -> tuple[SagaSmithApp, str]:
    """Create a campaign-backed SagaSmithApp with SafetyEventService bound."""
    root = tmp_path / "c"
    init_campaign(name="Safety Test", root=root, provider="fake")
    paths, m = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=m)
    conn = open_campaign_db(paths.db, read_only=False)
    app.safety_events = SafetyEventService(conn=conn)
    registry = CommandRegistry()
    registry.register(PauseCommand())
    registry.register(LineCommand())
    registry.register(SaveCommand())
    app.commands = registry  # type: ignore[assignment]
    return app, m.campaign_id


class FakeRuntime:
    """Records post_interrupt calls for testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[InterruptKind, dict[str, Any] | None]] = []

    @property
    def thread_config(self) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": "campaign:test"}}

    def post_interrupt(self, *, kind: InterruptKind, payload: dict[str, Any] | None = None) -> None:
        self.calls.append((kind, payload))


# ---------------------------------------------------------------------------
# Test 1: PauseCommand still writes SafetyEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_persists_safety_event(tmp_path: Path) -> None:
    """Phase 3 regression: /pause writes SafetyEvent."""
    app, campaign_id = _make_app_with_safety(tmp_path)

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

    from sagasmith.persistence.repositories import SafetyEventRepository

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].kind == "pause"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 2: PauseCommand posts PAUSE interrupt when graph bound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_posts_interrupt_when_graph_bound(tmp_path: Path) -> None:
    """Phase 4: /pause posts InterruptKind.PAUSE when graph_runtime is set."""
    app, _campaign_id = _make_app_with_safety(tmp_path)
    fake = FakeRuntime()
    app.graph_runtime = fake  # type: ignore[assignment]

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

    assert len(fake.calls) == 1
    kind, payload = fake.calls[0]
    assert kind == InterruptKind.PAUSE
    assert payload == {"reason": "player typed /pause"}


# ---------------------------------------------------------------------------
# Test 3: PauseCommand skips interrupt when graph unbound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_skips_interrupt_when_graph_unbound(tmp_path: Path) -> None:
    """Phase 3 compatibility: no crash when graph_runtime is None."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    app.graph_runtime = None

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "Paused." in combined

    from sagasmith.persistence.repositories import SafetyEventRepository

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].kind == "pause"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 4: LineCommand writes SafetyEvent AND posts LINE interrupt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_line_posts_interrupt_when_graph_bound(tmp_path: Path) -> None:
    """Phase 4: /line posts InterruptKind.LINE with topic payload."""
    app, campaign_id = _make_app_with_safety(tmp_path)
    fake = FakeRuntime()
    app.graph_runtime = fake  # type: ignore[assignment]

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/line graphic_violence":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

    # SafetyEvent still written
    from sagasmith.persistence.repositories import SafetyEventRepository

    conn = open_campaign_db(app.paths.db, read_only=True)
    try:
        rows = SafetyEventRepository(conn).list_for_campaign(campaign_id)
        assert len(rows) == 1
        assert rows[0].policy_ref == "graphic_violence"
    finally:
        conn.close()

    # Interrupt posted
    assert len(fake.calls) == 1
    kind, payload = fake.calls[0]
    assert kind == InterruptKind.LINE
    assert payload == {"topic": "graphic_violence"}


@pytest.mark.asyncio
async def test_quit_posts_session_end_interrupt(tmp_path: Path) -> None:
    """Phase 4: session end is represented as a graph interrupt before exit."""
    app, _campaign_id = _make_app_with_safety(tmp_path)
    fake = FakeRuntime()
    app.graph_runtime = fake  # type: ignore[assignment]

    await app.action_quit()

    assert len(fake.calls) == 1
    kind, payload = fake.calls[0]
    assert kind == InterruptKind.SESSION_END
    assert payload == {"reason": "player quit"}
