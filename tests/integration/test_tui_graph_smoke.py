"""End-to-end smoke test: TUI input → graph invocation → stub narration.

This is the consensus-requested regression from 04-REVIEWS.md — it proves
the full Phase 4 path works, not just that individual pieces compile.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from sagasmith.app.campaign import CampaignManifest
from sagasmith.app.paths import CampaignPaths
from sagasmith.graph.bootstrap import GraphBootstrap
from sagasmith.graph.interrupts import extract_pending_interrupt
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.services.safety import SafetyEventService
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import RetconCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand

pytestmark = pytest.mark.integration


def _seed_campaign(conn: sqlite3.Connection, manifest: CampaignManifest) -> None:
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (manifest.campaign_id, manifest.campaign_name, manifest.campaign_slug,
         datetime.now(UTC).isoformat(), "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("turn_000001", manifest.campaign_id, "session_001", "needs_vault_repair",
         datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), 1),
    )
    conn.commit()


@pytest.fixture
def wired_app(tmp_path):
    """Full TUI app wired to a real in-memory DB + GraphRuntime.

    Inserts a pre-existing turn_records row so FK constraints on
    checkpoint_refs/agent_skill_log pass during the test.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    manifest = CampaignManifest(
        campaign_id="cmp_smoke_001",
        campaign_name="Smoke Test",
        campaign_slug="smoke-test",
        created_at=datetime.now(UTC).isoformat(),
        sagasmith_version="0.0.1",
        schema_version=1,
        manifest_version=1,
    )
    _seed_campaign(conn, manifest)

    paths = CampaignPaths(
        root=tmp_path,
        db=tmp_path / "campaign.sqlite",
        manifest=tmp_path / "campaign.toml",
        player_vault=tmp_path / "player_vault",
    )
    app = SagaSmithApp(paths=paths, manifest=manifest)
    app.bind_service_connection(conn)
    app.safety_events = SafetyEventService(conn=conn)
    app.cost_governor = CostGovernor(session_budget_usd=1.0)
    app.current_turn_id = "turn_000001"

    dice_service = DiceService(
        campaign_seed=manifest.campaign_id,
        session_seed="session_001",
    )
    bootstrap = GraphBootstrap.from_services(
        dice=dice_service,
        cost=app.cost_governor,
        safety=app.safety_events,
        llm=None,
    )
    app.graph_runtime = build_persistent_graph(
        bootstrap, conn, campaign_id=manifest.campaign_id
    )

    registry = CommandRegistry()
    registry.register(PauseCommand())
    registry.register(LineCommand())
    registry.register(RetconCommand())
    app.commands = registry

    yield app, conn, manifest


async def test_tui_input_drives_graph_to_pre_narration(wired_app):
    app, conn, _manifest = wired_app
    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "roll perception":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        # Graph should be paused before orator
        snapshot = app.graph_runtime.graph.get_state(app.graph_runtime.thread_config)
        assert snapshot.next == ("orator",), f"Expected pause at orator, got next={snapshot.next}"

        # pre_narration checkpoint recorded
        cur = conn.execute(
            "SELECT kind FROM checkpoint_refs WHERE turn_id=?", ("turn_000001",)
        )
        kinds = [row[0] for row in cur.fetchall()]
        assert kinds == ["pre_narration"]

        # agent_skill_log has 2 rows (oracle, rules_lawyer)
        cur = conn.execute(
            "SELECT agent_name, outcome FROM agent_skill_log WHERE turn_id=? ORDER BY id",
            ("turn_000001",)
        )
        rows = cur.fetchall()
        assert [r[0] for r in rows] == ["oracle", "rules_lawyer"]
        assert all(r[1] == "success" for r in rows)


async def test_resume_completes_turn_with_stub_narration(wired_app):
    app, conn, manifest = wired_app
    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "roll perception":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        # Build a turn record matching the seeded row
        tr = TurnRecord(
            turn_id="turn_000001",
            campaign_id=manifest.campaign_id,
            session_id="session_001",
            status="needs_vault_repair",
            started_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(),
            schema_version=1,
        )
        app.graph_runtime.resume_and_close(tr)
        app._sync_narration_from_graph()
        app._sync_narration_from_graph()

        # Narration area received fallback (no LLM client in test)
        assert any("scene shifts" in line for line in app.narration.logged_lines)
        assert sum("scene shifts" in line for line in app.narration.logged_lines) == 1

        # Both checkpoints written
        cur = conn.execute(
            "SELECT kind FROM checkpoint_refs WHERE turn_id=? ORDER BY kind", ("turn_000001",)
        )
        assert [r[0] for r in cur.fetchall()] == ["final", "pre_narration"]

        # Turn marked complete
        cur = conn.execute("SELECT status FROM turn_records WHERE turn_id=?", ("turn_000001",))
        assert cur.fetchone()[0] == "complete"

        # 4 agent log rows
        cur = conn.execute(
            "SELECT agent_name FROM agent_skill_log WHERE turn_id=? ORDER BY id", ("turn_000001",)
        )
        assert [r[0] for r in cur.fetchall()] == ["oracle", "rules_lawyer", "orator", "archivist"]


async def test_pause_command_posts_interrupt_and_preserves_safety_event(wired_app):
    app, conn, manifest = wired_app
    async with app.run_test() as pilot:
        # Invoke /pause directly (no game turn yet)
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        # Graph has pending pause interrupt
        pending = extract_pending_interrupt(app.graph_runtime)
        assert pending is not None and pending["kind"] == "pause"

        # Phase 3 SafetyEvent regression preserved
        cur = conn.execute(
            "SELECT kind FROM safety_events WHERE campaign_id=? ORDER BY timestamp DESC LIMIT 1",
            (manifest.campaign_id,),
        )
        assert cur.fetchone()[0] == "pause"


async def test_resume_after_pause_completes_turn(wired_app):
    app, conn, manifest = wired_app
    async with app.run_test() as pilot:
        await pilot.click("#player-input")
        for ch in "roll perception":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        # Fire /pause on top of the pending orator interrupt
        await pilot.click("#player-input")
        for ch in "/pause":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        pending = extract_pending_interrupt(app.graph_runtime)
        assert pending is not None and pending["kind"] == "pause"

        # Clear pause then close
        app.graph_runtime.resume_after_interrupt()
        tr = TurnRecord(
            turn_id="turn_000001",
            campaign_id=manifest.campaign_id,
            session_id="session_001",
            status="needs_vault_repair",
            started_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(),
            schema_version=1,
        )
        app.graph_runtime.resume_and_close(tr)
        app._sync_narration_from_graph()

        cur = conn.execute("SELECT status FROM turn_records WHERE turn_id=?", ("turn_000001",))
        assert cur.fetchone()[0] == "complete"
