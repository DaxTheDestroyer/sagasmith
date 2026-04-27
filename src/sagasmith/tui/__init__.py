"""TUI package \u2014 Textual widgets, screens, and UI event handling."""

from sagasmith.tui.app import CommandInvoked, PlayerInputSubmitted, SagaSmithApp
from sagasmith.tui.commands.help import HelpCommand
from sagasmith.tui.commands.registry import CommandRegistry, TUICommand
from sagasmith.tui.runtime import build_app
from sagasmith.tui.state import StatusSnapshot, TUIState

__all__ = [
    "CommandInvoked",
    "CommandRegistry",
    "HelpCommand",
    "PlayerInputSubmitted",
    "SagaSmithApp",
    "StatusSnapshot",
    "TUICommand",
    "TUIState",
    "build_app",
]
