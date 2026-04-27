"""NarrationArea widget \u2014 append-only scrollable transcript log."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import RichLog


class NarrationArea(Widget):
    """Append-only scrollable transcript region.

    Uses RichLog with markup=False to prevent Rich escape-sequence injection
    from transcript content (T-03-17 mitigation).

    ``_logged_lines`` is a plain list tracking every line written via
    ``append_line()`` \u2014 used by tests to verify command output without
    inspecting Textual's internal rendering state.
    """

    DEFAULT_CSS = """
    NarrationArea { height: 1fr; border: solid $primary; }
    """

    def compose(self):  # type: ignore[override]
        self.logged_lines: list[str] = []
        yield RichLog(
            id="narration-log",
            wrap=True,
            highlight=False,
            markup=False,
            auto_scroll=True,
        )

    def append_line(self, text: str) -> None:
        log = self.query_one("#narration-log", RichLog)
        log.write(text)
        if not hasattr(self, "logged_lines"):
            self.logged_lines = []
        self.logged_lines.append(text)

    def load_scrollback(self, lines: list[str]) -> None:
        log = self.query_one("#narration-log", RichLog)
        for line in lines:
            log.write(line)
