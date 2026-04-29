"""Tests for control commands: save, recap, inventory, map, clock, budget, retcon."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.repositories import TranscriptRepository, TurnRecordRepository
from sagasmith.schemas.persistence import TranscriptEntry, TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import (
    BudgetCommand,
    ClockCommand,
    InventoryCommand,
    MapCommand,
    RecapCommand,
    SaveCommand,
)
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.state import StatusSnapshot
from sagasmith.tui.widgets.narration import NarrationArea


def _make_app(tmp_path: Path) -> SagaSmithApp:
    root = tmp_path / "c"
    init_campaign(name="Ctrl Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=manifest)
    registry = CommandRegistry()
    app.commands = registry  # type: ignore[assignment]
    return app


# ---------------------------------------------------------------------------
# Stub commands — each should append a narration line with the command name
# and the correct phase reference
# ---------------------------------------------------------------------------

_STUB_CASES = [
    (SaveCommand(), "/save", "Phase 4"),
    (InventoryCommand(), "/inventory", "Phase 5"),
    (MapCommand(), "/map", "Phase 5"),
]


class _FakeSnapshot:
    def __init__(self) -> None:
        self.values = {"rolling_summary": "Mara guided the hero through the river fog."}


class _FakeGraph:
    def get_state(self, thread_config: object) -> _FakeSnapshot:
        return _FakeSnapshot()


class _FakeGraphRuntime:
    graph = _FakeGraph()
    thread_config: ClassVar[dict[str, object]] = {}


@pytest.mark.asyncio
@pytest.mark.parametrize("cmd,cmd_name,phase_ref", _STUB_CASES)
async def test_each_stub_command_appends_expected_prefix(
    tmp_path: Path,
    cmd: object,
    cmd_name: str,
    phase_ref: str,
) -> None:
    """Each stub command writes a narration line with the command name and phase reference."""
    app = _make_app(tmp_path)
    logged: list[str] = []
    async with app.run_test():
        cmd.handle(app, ())  # type: ignore[attr-defined]
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert cmd_name in combined, f"Expected {cmd_name!r} in narration; got: {logged}"
    assert phase_ref in combined, f"Expected {phase_ref!r} in narration; got: {logged}"


@pytest.mark.asyncio
async def test_clock_command_renders_state_default(tmp_path: Path) -> None:
    """Dispatch /clock on a fresh app → narration contains 'Clock: —'."""
    app = _make_app(tmp_path)
    logged: list[str] = []
    async with app.run_test():
        ClockCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any("Clock: \u2014" in line for line in logged), f"Expected 'Clock: —' in {logged}"


@pytest.mark.asyncio
async def test_recap_command_renders_summary_and_recent_transcript(tmp_path: Path) -> None:
    """RecapCommand renders rolling_summary followed by recent transcript rows."""
    app = _make_app(tmp_path)
    conn = open_campaign_db(app.paths.db)
    app.bind_service_connection(conn)
    app.graph_runtime = _FakeGraphRuntime()  # type: ignore[assignment]
    repo = TranscriptRepository(conn)
    turns = TurnRecordRepository(conn)
    entries: list[tuple[Literal["player_input", "narration_final", "system_note"], str]] = [
        ("player_input", "I look for Mara."),
        ("narration_final", "You find tracks by the dock."),
        ("player_input", "I follow them."),
        ("narration_final", "Mara steps from the fog."),
    ]
    for index, (kind, content) in enumerate(entries):
        turn_id = f"turn_{index:06d}"
        turns.upsert(
            TurnRecord(
                turn_id=turn_id,
                campaign_id=app.manifest.campaign_id,
                session_id="session_001",
                status="complete",
                started_at=f"2026-04-29T00:0{index}:00Z",
                completed_at=f"2026-04-29T00:0{index}:30Z",
                schema_version=1,
            )
        )
        repo.append(
            TranscriptEntry(
                turn_id=turn_id,
                kind=kind,
                content=content,
                sequence=index,
                created_at="2026-04-29T00:00:00Z",
            )
        )
    conn.commit()

    logged: list[str] = []
    async with app.run_test():
        RecapCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "=== RECAP ===" in combined
    assert "Mara guided the hero through the river fog." in combined
    assert "> I look for Mara." in combined
    assert "Mara steps from the fog." in combined


@pytest.mark.asyncio
async def test_recap_command_excludes_retconned_transcript(tmp_path: Path) -> None:
    """RecapCommand must not display transcript rows from retconned turns."""
    app = _make_app(tmp_path)
    conn = open_campaign_db(app.paths.db)
    app.bind_service_connection(conn)
    app.graph_runtime = _FakeGraphRuntime()  # type: ignore[assignment]
    turns = TurnRecordRepository(conn)
    transcripts = TranscriptRepository(conn)
    for turn_id, status, content in [
        ("turn_000001", "complete", "Canonical event remains."),
        ("turn_000002", "retconned", "Removed canon must stay hidden."),
    ]:
        turns.upsert(
            TurnRecord(
                turn_id=turn_id,
                campaign_id=app.manifest.campaign_id,
                session_id="session_001",
                status=status,  # type: ignore[arg-type]
                started_at="2026-04-29T00:00:00Z",
                completed_at="2026-04-29T00:01:00Z",
                schema_version=1,
            )
        )
        transcripts.append(
            TranscriptEntry(
                turn_id=turn_id,
                kind="narration_final",
                content=content,
                sequence=0,
                created_at="2026-04-29T00:01:00Z",
            )
        )
    conn.commit()

    logged: list[str] = []
    async with app.run_test():
        RecapCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "Canonical event remains." in combined
    assert "Removed canon must stay hidden." not in combined


@pytest.mark.asyncio
async def test_clock_command_renders_state_filled(tmp_path: Path) -> None:
    """Set status with clock data → /clock shows Day X, HH:MM."""
    app = _make_app(tmp_path)
    logged: list[str] = []
    async with app.run_test():
        app.state.status = StatusSnapshot(clock_day=3, clock_hhmm="14:30")
        ClockCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any("Day 3, 14:30" in line for line in logged), f"Expected 'Day 3, 14:30' in {logged}"


@pytest.mark.asyncio
async def test_budget_command_without_governor_says_no_session(tmp_path: Path) -> None:
    """app.cost_governor = None → narration contains 'no session governor'."""
    app = _make_app(tmp_path)
    logged: list[str] = []
    async with app.run_test():
        app.cost_governor = None
        BudgetCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any("no session governor" in line for line in logged), (
        f"Expected no session governor msg; got: {logged}"
    )


@pytest.mark.asyncio
async def test_budget_command_with_governor_renders_inspection(tmp_path: Path) -> None:
    """BudgetCommand with a CostGovernor renders '$1.00', 'warnings_sent=[]', 'hard_stopped=False'."""
    app = _make_app(tmp_path)
    logged: list[str] = []
    async with app.run_test():
        app.cost_governor = CostGovernor(session_budget_usd=1.00)
        BudgetCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "$1.00" in combined, f"Expected '$1.00' in {logged}"
    assert "warnings_sent=[]" in combined, f"Expected 'warnings_sent=[]' in {logged}"
    assert "hard_stopped=False" in combined, f"Expected 'hard_stopped=False' in {logged}"
