"""Built-in /help command \u2014 lists all registered slash commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp
    from sagasmith.tui.commands.registry import CommandRegistry


@dataclass(frozen=True)
class HelpCommand:
    """List all registered slash commands in the narration area.

    Takes the registry as a constructor argument so it automatically picks
    up commands registered by Plan 03-04 without any code changes here.
    """

    registry: CommandRegistry
    name: str = "help"
    description: str = "List all available slash commands."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        from sagasmith.tui.widgets.narration import NarrationArea

        narration = app.query_one(NarrationArea)
        narration.append_line("Available commands:")
        for command in self.registry.all():
            narration.append_line(f"  /{command.name} \u2014 {command.description}")
