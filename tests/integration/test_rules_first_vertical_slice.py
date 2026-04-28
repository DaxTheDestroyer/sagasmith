"""End-to-end no-paid-call rules-first vertical-slice regression."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

import pytest

from sagasmith.app.campaign import CampaignManifest
from sagasmith.app.paths import CampaignPaths
from sagasmith.graph.bootstrap import GraphBootstrap
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.mechanics import CheckResult, CombatState, RollResult
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.services.safety import SafetyEventService
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import RetconCommand, SheetCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.safety import LineCommand, PauseCommand
from sagasmith.tui.widgets.status_panel import format_status_snapshot

pytestmark = pytest.mark.integration


def _seed_campaign(conn: sqlite3.Connection, manifest: CampaignManifest) -> None:
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            manifest.campaign_id,
            manifest.campaign_name,
            manifest.campaign_slug,
            datetime.now(UTC).isoformat(),
            "0.0.1",
            1,
        ),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "turn_000001",
            manifest.campaign_id,
            "session_001",
            "needs_vault_repair",
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat(),
            1,
        ),
    )
    conn.commit()


@pytest.fixture
def rules_first_app(tmp_path):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    manifest = CampaignManifest(
        campaign_id="cmp_rules_first_001",
        campaign_name="Rules First Test",
        campaign_slug="rules-first-test",
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

    dice_service = DiceService(campaign_seed=manifest.campaign_id, session_seed="session_001")
    bootstrap = GraphBootstrap.from_services(
        dice=dice_service,
        cost=app.cost_governor,
        safety=app.safety_events,
        llm=None,
    )
    app.graph_runtime = build_persistent_graph(bootstrap, conn, campaign_id=manifest.campaign_id)

    registry = CommandRegistry()
    registry.register(SheetCommand())
    registry.register(PauseCommand())
    registry.register(LineCommand())
    registry.register(RetconCommand())
    app.commands = registry

    yield app, conn, manifest


def _snapshot_values(app: SagaSmithApp) -> dict[str, Any]:
    assert app.graph_runtime is not None
    snapshot = app.graph_runtime.graph.get_state(app.graph_runtime.thread_config)
    return dict(snapshot.values or {})


def _check_results(values: dict[str, Any]) -> list[CheckResult]:
    return [CheckResult.model_validate(item) for item in values.get("check_results", [])]


def _combat_state(values: dict[str, Any]) -> CombatState:
    return CombatState.model_validate(values["combat_state"])


async def _submit(pilot, text: str) -> None:
    await pilot.click("#player-input")
    for ch in text:
        await pilot.press(ch)
    await pilot.press("enter")
    await pilot.pause()


async def test_rules_first_vertical_slice_sheet_check_reveal_and_combat(rules_first_app) -> None:
    app, _conn, manifest = rules_first_app
    assert app.graph_runtime is not None
    assert app.graph_runtime.bootstrap.services.llm is None

    async with app.run_test() as pilot:
        await _submit(pilot, "/sheet")
        sheet_output = "\n".join(app.narration.logged_lines)
        assert "Character Sheet" in sheet_output
        assert "Valeros" in sheet_output

        await _submit(pilot, "roll athletics dc 15")
        check_values = _snapshot_values(app)
        check_results = _check_results(check_values)
        assert len(check_results) == 1
        skill_result = check_results[0]
        assert skill_result.roll_result.roll_id.startswith("roll_")
        check_output = "\n".join(app.narration.logged_lines)
        assert "CheckResult" in check_output
        assert "Saved to roll log:" in check_output
        assert skill_result.roll_result.roll_id in check_output

        await _submit(pilot, "start combat")
        start_values = _snapshot_values(app)
        start_combat = _combat_state(start_values)
        start_results = _check_results(start_values)
        initiative_roll_ids = [result.roll_result.roll_id for result in start_results[1:]]
        assert start_combat.initiative_order
        assert all(roll_id.startswith("roll_") for roll_id in initiative_roll_ids)

        resumed_start_values = _snapshot_values(app)
        resumed_start_combat = _combat_state(resumed_start_values)
        resumed_start_results = _check_results(resumed_start_values)
        assert resumed_start_combat.initiative_order == start_combat.initiative_order
        assert [result.roll_result.roll_id for result in resumed_start_results] == [
            result.roll_result.roll_id for result in start_results
        ]

        while resumed_start_combat.active_combatant_id != "pc_valeros_first_slice":
            await _submit(pilot, "end turn")
            resumed_start_combat = _combat_state(_snapshot_values(app))

        await _submit(pilot, "strike enemy_weak_melee with longsword")
        strike_values = _snapshot_values(app)
        strike_combat = _combat_state(strike_values)
        strike_results = _check_results(strike_values)
        attack_result = strike_results[-1]
        assert attack_result.roll_result.roll_id.startswith("roll_attack_longsword_")
        damage_roll_ids = [
            effect.description.split("damage_roll=", 1)[1].split(";", 1)[0].rstrip(")")
            for effect in attack_result.effects
            if "damage_roll=" in effect.description
        ]
        assert damage_roll_ids
        target_hp = next(
            combatant.current_hp
            for combatant in strike_combat.combatants
            if combatant.id == "enemy_weak_melee"
        )

        resumed_strike_values = _snapshot_values(app)
        resumed_strike_combat = _combat_state(resumed_strike_values)
        resumed_strike_results = _check_results(resumed_strike_values)
        resumed_attack = CheckResult.model_validate(resumed_strike_results[-1])
        assert resumed_attack.roll_result.roll_id == attack_result.roll_result.roll_id
        assert damage_roll_ids[0] in "\n".join(app.narration.logged_lines)
        assert damage_roll_ids[0] in "\n".join(
            effect.description for effect in resumed_attack.effects
        )
        assert next(
            combatant.current_hp
            for combatant in resumed_strike_combat.combatants
            if combatant.id == "enemy_weak_melee"
        ) == target_hp

        rendered_status = format_status_snapshot(app.state.status)
        rendered_output = "\n".join([*app.narration.logged_lines, rendered_status])
        assert manifest.campaign_id == "cmp_rules_first_001"
        assert "Round: 1" in rendered_output
        assert "Actions: 2/3" in rendered_output
        assert "damage_roll=roll_" in rendered_output
        assert "HP" in rendered_output
