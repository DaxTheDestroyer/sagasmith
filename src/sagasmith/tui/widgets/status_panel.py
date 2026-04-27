"""StatusPanel widget \u2014 renders a StatusSnapshot dataclass."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from sagasmith.tui.state import StatusSnapshot


class StatusPanel(Widget):
    """Right-side status panel showing HP, conditions, quest, location, clock, and last rolls."""

    DEFAULT_CSS = """
    StatusPanel { width: 32; border: solid $accent; padding: 1; }
    """

    snapshot: reactive[StatusSnapshot] = reactive(StatusSnapshot(), always_update=True)

    def compose(self):  # type: ignore[override]
        yield Static(id="status-body")

    def watch_snapshot(self, new: StatusSnapshot) -> None:
        body = self.query_one("#status-body", Static)
        body.update(self._format_snapshot(new))

    def _format_snapshot(self, s: StatusSnapshot) -> str:
        lines = [
            s.format_hp(),
            "Conditions: " + (", ".join(s.conditions) if s.conditions else "\u2014"),
            f"Quest: {s.active_quest or '\u2014'}",
            f"Location: {s.location or '\u2014'}",
            s.format_clock(),
            "Last rolls:",
            *[f"  {r}" for r in (s.last_rolls or ("\u2014",))[:3]],
        ]
        return "\n".join(lines)
