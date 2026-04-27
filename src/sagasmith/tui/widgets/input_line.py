"""InputLine widget \u2014 Textual Input with Enter-submit handler."""

from __future__ import annotations

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input


class InputLine(Widget):
    """Bottom-docked input widget that posts a Submitted message on Enter."""

    DEFAULT_CSS = """
    InputLine { dock: bottom; height: 3; }
    """

    class Submitted(Message):
        """Posted when the player presses Enter with a non-empty value."""

        def __init__(self, raw: str) -> None:
            self.raw = raw
            super().__init__()

    def compose(self):  # type: ignore[override]
        yield Input(
            id="player-input",
            placeholder="Type action or /command then Enter\u2026",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""  # clear field immediately
        if raw:
            self.post_message(self.Submitted(raw))
