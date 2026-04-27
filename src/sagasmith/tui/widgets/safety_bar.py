"""SafetyBar widget \u2014 persistent top bar showing /pause /line affordances."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static


class SafetyBar(Widget):
    """Docked top bar showing persistent safety tool affordances."""

    DEFAULT_CSS = """
    SafetyBar { dock: top; height: 1; background: $warning-darken-1; }
    """

    def compose(self):  # type: ignore[override]
        yield Static(
            "SAFETY: /pause  /line   (persistent controls \u2014 type to activate)",
            id="safety-text",
        )
