"""CommandRegistry and TUICommand protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp


@runtime_checkable
class TUICommand(Protocol):
    """Protocol that every slash command must satisfy.

    Plan 03-04 registers concrete commands against this protocol.
    CommandRegistry is the ONLY extension point — app.py needs zero changes.
    """

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None: ...


class CommandRegistry:
    """Registry mapping command names to TUICommand implementations."""

    def __init__(self) -> None:
        self._by_name: dict[str, TUICommand] = {}

    def register(self, command: TUICommand) -> None:
        """Register a command. Raises ValueError on duplicate name."""
        if command.name in self._by_name:
            raise ValueError(f"duplicate command: {command.name}")
        self._by_name[command.name] = command

    def get(self, name: str) -> TUICommand | None:
        """Return command by name, or None if not registered."""
        return self._by_name.get(name)

    def names(self) -> list[str]:
        """Return sorted list of all registered command names."""
        return sorted(self._by_name.keys())

    def all(self) -> list[TUICommand]:
        """Return all commands in sorted name order."""
        return [self._by_name[n] for n in self.names()]

    def dispatch(self, app: SagaSmithApp, name: str, args: tuple[str, ...]) -> None:
        """Dispatch command by name. Writes error line to narration if unknown."""
        from sagasmith.tui.widgets.narration import NarrationArea

        command = self.get(name)
        if command is None:
            narration = app.query_one(NarrationArea)
            narration.append_line(f"Unknown command: /{name}. Type /help for a list.")
            return
        command.handle(app, args)
