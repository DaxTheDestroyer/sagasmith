"""Tests for the /settings command (ONBD-05 cross-plan verification)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.onboarding.store import OnboardingStore, OnboardingTriple
from sagasmith.onboarding.wizard import OnboardingWizard
from sagasmith.persistence.db import open_campaign_db
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.commands.settings import SettingsCommand
from sagasmith.tui.widgets.narration import NarrationArea
from tests.onboarding.fixtures import make_happy_path_answers


def _make_triple() -> OnboardingTriple:
    wizard = OnboardingWizard()
    for answer in make_happy_path_answers():
        wizard.step(answer)
    profile, policy, rules = wizard.build_records()
    return OnboardingTriple(player_profile=profile, content_policy=policy, house_rules=rules)


def _make_app(tmp_path: Path, *, bind_store: bool = True) -> tuple[SagaSmithApp, str]:
    root = tmp_path / "c"
    init_campaign(name="Settings Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=manifest)
    if bind_store:
        conn = open_campaign_db(paths.db, read_only=False)
        app.onboarding_store = OnboardingStore(conn=conn)
    registry = CommandRegistry()
    registry.register(SettingsCommand())
    app.commands = registry  # type: ignore[assignment]
    return app, manifest.campaign_id


@pytest.mark.asyncio
async def test_settings_without_triple_says_run_onboarding(tmp_path: Path) -> None:
    """No committed triple → narration contains 'no onboarding triple found'."""
    app, _ = _make_app(tmp_path, bind_store=True)
    logged: list[str] = []
    async with app.run_test():
        SettingsCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any(
        "no onboarding triple found" in line for line in logged
    ), f"Expected no-triple msg; got: {logged}"


@pytest.mark.asyncio
async def test_settings_with_triple_renders_summary(tmp_path: Path) -> None:
    """Committed triple → narration contains genre=, pacing=, content_policy, house_rules, budget=."""
    app, campaign_id = _make_app(tmp_path, bind_store=True)

    # Commit a happy-path triple via OnboardingStore
    assert app.onboarding_store is not None
    triple = _make_triple()
    app.onboarding_store.commit(campaign_id, triple)

    logged: list[str] = []
    async with app.run_test():
        SettingsCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "genre=" in combined, f"Expected 'genre=' in: {logged}"
    assert "pacing=" in combined, f"Expected 'pacing=' in: {logged}"
    assert "content_policy:" in combined, f"Expected 'content_policy:' in: {logged}"
    assert "house_rules:" in combined, f"Expected 'house_rules:' in: {logged}"
    assert "budget=" in combined, f"Expected 'budget=' in: {logged}"


@pytest.mark.asyncio
async def test_settings_without_store_is_noop(tmp_path: Path) -> None:
    """onboarding_store=None → narration says 'onboarding store not bound'; no exception."""
    app, _ = _make_app(tmp_path, bind_store=False)
    logged: list[str] = []
    async with app.run_test():
        SettingsCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    assert any(
        "onboarding store not bound" in line for line in logged
    ), f"Expected store-not-bound msg; got: {logged}"
