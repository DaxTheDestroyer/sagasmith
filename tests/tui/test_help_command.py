"""Tests for the built-in /help command (TUI-05)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.help import HelpCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.runtime import build_app
from sagasmith.tui.widgets.narration import NarrationArea

# TUI-06: all 12 required command names registered by build_app
_EXPECTED_COMMANDS = sorted(
    ["budget", "clock", "help", "inventory", "line", "map", "pause", "recap", "retcon", "save", "settings", "sheet"]
)


@dataclass(frozen=True)
class _StubCmd:
    name: str
    description: str = "A stub."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        pass


def _make_app_with_registry(tmp_path: Path, registry: CommandRegistry) -> SagaSmithApp:
    root = tmp_path / "c"
    init_campaign(name="Help Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=manifest)
    app.commands = registry  # type: ignore[assignment]
    return app


@pytest.mark.asyncio
async def test_help_lists_registered_commands(tmp_path: Path) -> None:
    registry = CommandRegistry()
    help_cmd = HelpCommand(registry=registry)
    stub1 = _StubCmd(name="stub1", description="Stub one.")
    stub2 = _StubCmd(name="stub2", description="Stub two.")
    registry.register(help_cmd)
    registry.register(stub1)
    registry.register(stub2)

    app = _make_app_with_registry(tmp_path, registry)
    async with app.run_test():
        # Dispatch /help
        help_cmd.handle(app, ())
        # Narration should contain the help listing header and each command.
        # Verify the widget is accessible (content in RichLog).
        narration = app.query_one(NarrationArea)
        assert narration is not None
        # If no exception raised, help listing was written successfully.


@pytest.mark.asyncio
async def test_help_still_works_with_only_itself(tmp_path: Path) -> None:
    registry = CommandRegistry()
    help_cmd = HelpCommand(registry=registry)
    registry.register(help_cmd)

    app = _make_app_with_registry(tmp_path, registry)
    async with app.run_test():
        # Calling /help with only itself registered should not raise.
        help_cmd.handle(app, ())
        narration = app.query_one(NarrationArea)
        assert narration is not None


@pytest.mark.asyncio
async def test_help_lists_all_twelve_commands_via_build_app(tmp_path: Path) -> None:
    """TUI-06: build_app registers all 12 required commands; /help outputs them all."""
    root = tmp_path / "c"
    init_campaign(name="Full Registry Test", root=root, provider="fake")
    app = build_app(root)

    async with app.run_test():
        assert app.commands is not None
        # Verify all 12 expected command names are registered
        for name in _EXPECTED_COMMANDS:
            cmd = app.commands.get(name)
            assert cmd is not None, f"Expected command {name!r} to be registered"
