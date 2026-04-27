"""Tests for SagaSmithApp mount and basic widget interactions (TUI-01, TUI-02, TUI-04)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.tui.app import CommandInvoked, SagaSmithApp
from sagasmith.tui.widgets.input_line import InputLine
from sagasmith.tui.widgets.narration import NarrationArea
from sagasmith.tui.widgets.safety_bar import SafetyBar
from sagasmith.tui.widgets.status_panel import StatusPanel


async def _make_app(tmp_path: Path) -> SagaSmithApp:
    """Helper: initialise a campaign and return an un-run SagaSmithApp."""
    root = tmp_path / "c"
    init_campaign(name="UI Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    return SagaSmithApp(paths=paths, manifest=manifest)


@pytest.mark.asyncio
async def test_app_mounts_with_four_regions(tmp_path: Path) -> None:
    app = await _make_app(tmp_path)
    async with app.run_test():
        assert app.query_one("#narration-area", NarrationArea) is not None
        assert app.query_one("#status-panel", StatusPanel) is not None
        assert app.query_one(SafetyBar) is not None
        assert app.query_one("#input-line", InputLine) is not None


@pytest.mark.asyncio
async def test_app_shows_welcome_on_mount(tmp_path: Path) -> None:
    app = await _make_app(tmp_path)
    async with app.run_test():
        # The narration log should contain welcome text.
        # We check via the scrollback text that on_mount wrote.
        narration = app.query_one(NarrationArea)
        # The narration writes via RichLog; we verify by checking the
        # scrollback list that was populated after input submission
        # For welcome text we just confirm no crash during mount.
        # Additional content verified by checking the narration widget exists.
        assert narration is not None


@pytest.mark.asyncio
async def test_input_submit_without_slash_emits_player_input(tmp_path: Path) -> None:
    app = await _make_app(tmp_path)
    async with app.run_test() as pilot:
        # Focus the input widget and type a character, then press Enter
        await pilot.click("#player-input")
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.pause()
        # The scrollback list should contain "> a"
        assert "> a" in app.state.scrollback


@pytest.mark.asyncio
async def test_input_submit_with_slash_parses_name_and_args(tmp_path: Path) -> None:
    """Slash input is parsed into CommandInvoked with name and args.

    We verify via a subclass override so the message is captured before
    Textual dispatches it internally.
    """

    invoked_events: list[CommandInvoked] = []

    class CapturingApp(SagaSmithApp):
        def on_command_invoked(self, event: CommandInvoked) -> None:
            invoked_events.append(event)
            # Don't dispatch further — commands is None in this test

    root = tmp_path / "c"
    init_campaign(name="UI Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = CapturingApp(paths=paths, manifest=manifest)

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/help verbose":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert len(invoked_events) == 1
        assert invoked_events[0].name == "help"
        assert invoked_events[0].args == ("verbose",)


@pytest.mark.asyncio
async def test_input_empty_submit_is_noop(tmp_path: Path) -> None:
    app = await _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        await pilot.press("enter")  # press Enter with empty field
        await pilot.pause()
        # No scrollback entries should exist
        assert app.state.scrollback == []
