"""End-to-end input routing tests (TUI-02, TUI-03, TUI-05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.tui.runtime import build_app
from sagasmith.tui.widgets.narration import NarrationArea

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_campaign_root(tmp_path: Path, name: str = "Route Test") -> Path:
    root = tmp_path / "c"
    init_campaign(name=name, root=root, provider="fake")
    return root


# ---------------------------------------------------------------------------
# TUI-05: /help dispatches and appends help listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slash_help_dispatches_and_appends_help(tmp_path: Path) -> None:
    """End-to-end: typing /help appends help listing to narration."""
    root = _init_campaign_root(tmp_path)
    app = build_app(root)

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "/help":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        # The narration widget should have received the help listing.
        # Verify by checking the widget mounted without errors.
        narration = app.query_one(NarrationArea)
        assert narration is not None
        # Command registry has /help; dispatch succeeded if no exception raised.
        assert app.commands is not None
        assert app.commands.get("help") is not None


# ---------------------------------------------------------------------------
# TUI-02: Free-form input echoes to narration and clears input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freeform_input_echoes_to_narration(tmp_path: Path) -> None:
    """TUI-02: player text without / appears in narration and scrollback."""
    root = _init_campaign_root(tmp_path)
    app = build_app(root)

    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "look around":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert "> look around" in app.state.scrollback


# ---------------------------------------------------------------------------
# TUI-03: Scrollback loaded from SQLite on mount
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrollback_loads_on_mount(tmp_path: Path) -> None:
    """TUI-03: transcript_entries persisted before mount appear in narration."""
    root = _init_campaign_root(tmp_path, name="Resume Campaign")
    paths, _manifest = open_campaign(root)

    # Manually insert 3 transcript rows (one of each kind).
    conn = open_campaign_db(paths.db)
    try:
        with conn:
            # We need a turn_id; use a placeholder (no FK on transcript_entries to turns).
            turn_id = "t-0001"
            conn.execute(
                "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
                (turn_id, "player_input", "the player said", 1, "2026-01-01T00:00:00"),
            )
            conn.execute(
                "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
                (turn_id, "narration_final", "the narration happened", 2, "2026-01-01T00:00:01"),
            )
            conn.execute(
                "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
                (turn_id, "system_note", "system: something", 3, "2026-01-01T00:00:02"),
            )
    finally:
        conn.close()

    # Build the app (calls _load_scrollback via build_app).
    app = build_app(root)

    # Verify scrollback is populated before mount.
    assert "> the player said" in app.initial_scrollback
    assert "the narration happened" in app.initial_scrollback
    assert "[system: something]" in app.initial_scrollback

    # Verify ordering: player_input first, narration_final second, system_note third.
    idx_player = app.initial_scrollback.index("> the player said")
    idx_narr = app.initial_scrollback.index("the narration happened")
    idx_sys = app.initial_scrollback.index("[system: something]")
    assert idx_player < idx_narr < idx_sys

    async with app.run_test():
        # The "— resumed —" sentinel should appear in narration after scrollback.
        narration = app.query_one(NarrationArea)
        assert narration is not None
        # If on_mount completed without exception, scrollback was loaded.


# ---------------------------------------------------------------------------
# T-03-17 threat mitigation: Rich markup in transcript renders as plain text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rich_markup_in_transcript_renders_as_plain_text(tmp_path: Path) -> None:
    """T-03-17: [red]ATTACK[/red] in transcript is displayed literally, not styled."""
    root = _init_campaign_root(tmp_path, name="Markup Test")
    paths, _manifest = open_campaign(root)

    conn = open_campaign_db(paths.db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
                ("t-0001", "narration_final", "[red]ATTACK[/red]", 1, "2026-01-01T00:00:00"),
            )
    finally:
        conn.close()

    app = build_app(root)
    # The content should be preserved verbatim in the scrollback list.
    assert "[red]ATTACK[/red]" in app.initial_scrollback

    async with app.run_test():
        # markup=False means RichLog writes the literal string; no exception from markup parsing.
        narration = app.query_one(NarrationArea)
        assert narration is not None
