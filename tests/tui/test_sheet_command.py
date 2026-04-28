"""Tests for the Phase 5 /sheet mechanics surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.rules.first_slice import make_first_slice_character
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import SheetCommand
from sagasmith.tui.widgets.narration import NarrationArea
from sagasmith.tui.widgets.sheet import render_character_sheet


def _make_app(tmp_path: Path) -> SagaSmithApp:
    root = tmp_path / "c"
    init_campaign(name="Sheet Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    return SagaSmithApp(paths=paths, manifest=manifest)


class _Snapshot:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values


class _Graph:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values

    def get_state(self, config: dict[str, dict[str, str]]) -> _Snapshot:
        return _Snapshot(self.values)


class _Runtime:
    def __init__(self, values: dict[str, object]) -> None:
        self.graph = _Graph(values)
        self.thread_config = {"configurable": {"thread_id": "campaign:test"}}


def test_render_character_sheet_contains_required_groups_in_order() -> None:
    text = render_character_sheet(make_first_slice_character())

    headings = [
        "Character Sheet",
        "Identity",
        "Durability",
        "Perception and saves",
        "Skills",
        "Attacks",
        "Inventory",
        "Esc closes sheet. Type an action when ready.",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "HP: 20/20" in text
    assert "AC: 18" in text
    assert "longsword: +7, 1d8+4 slashing" in text


@pytest.mark.asyncio
async def test_sheet_command_uses_live_graph_character_sheet_hp(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    live_sheet = make_first_slice_character().model_copy(update={"current_hp": 13})
    app.graph_runtime = _Runtime({"character_sheet": live_sheet.model_dump()})  # type: ignore[assignment]

    async with app.run_test():
        SheetCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "Character Sheet" in combined
    assert "Identity" in combined
    assert "Durability" in combined
    assert "Perception and saves" in combined
    assert "Skills" in combined
    assert "Attacks" in combined
    assert "Inventory" in combined
    assert "13/20" in combined
    assert "20/20" not in combined


@pytest.mark.asyncio
async def test_sheet_command_falls_back_when_live_sheet_is_invalid(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    app.graph_runtime = _Runtime({"character_sheet": {"current_hp": 13}})  # type: ignore[assignment]

    async with app.run_test():
        SheetCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "Character Sheet" in combined
    assert "20/20" in combined
    assert "/sheet (stub" not in combined
