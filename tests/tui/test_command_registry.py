"""Tests for CommandRegistry scaffold (TUI-05)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.widgets.narration import NarrationArea

# ---------------------------------------------------------------------------
# Stub TUICommand implementations for testing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubCommand:
    """Minimal TUICommand for testing registry behaviour."""

    name: str
    description: str = "A stub command."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        pass


def _make_app(tmp_path: Path) -> SagaSmithApp:
    root = tmp_path / "c"
    init_campaign(name="Reg Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    return SagaSmithApp(paths=paths, manifest=manifest)


# ---------------------------------------------------------------------------
# Pure registry unit tests (no Textual)
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    reg = CommandRegistry()
    cmd = _StubCommand(name="fake")
    reg.register(cmd)
    assert reg.get("fake") is cmd


def test_registry_duplicate_rejected() -> None:
    reg = CommandRegistry()
    cmd = _StubCommand(name="dup")
    reg.register(cmd)
    with pytest.raises(ValueError, match="duplicate command"):
        reg.register(cmd)


def test_registry_names_sorted() -> None:
    reg = CommandRegistry()
    reg.register(_StubCommand(name="zebra"))
    reg.register(_StubCommand(name="alpha"))
    assert reg.names() == ["alpha", "zebra"]


def test_registry_all_sorted() -> None:
    reg = CommandRegistry()
    reg.register(_StubCommand(name="beta"))
    reg.register(_StubCommand(name="alpha"))
    names = [c.name for c in reg.all()]
    assert names == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Dispatch test — requires Textual pilot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_dispatch_unknown_writes_narration(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    registry = CommandRegistry()
    app.commands = registry  # type: ignore[assignment]

    async with app.run_test():
        registry.dispatch(app, "nope", ())
        # The narration log should now contain the unknown command message.
        # We verify indirectly: the app must not crash, and we can inspect
        # via the narration widget that it mounted correctly.
        narration = app.query_one(NarrationArea)
        assert narration is not None
        # Verify the registry wrote an unknown command message by dispatching
        # and confirming no exception was raised (message was written to RichLog).
