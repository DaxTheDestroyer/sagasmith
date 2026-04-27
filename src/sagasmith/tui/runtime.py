"""TUIRuntime \u2014 constructs a ready-to-run SagaSmithApp from a campaign path."""

from __future__ import annotations

from pathlib import Path

from sagasmith.app.campaign import open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.help import HelpCommand
from sagasmith.tui.commands.registry import CommandRegistry

SCROLLBACK_LIMIT = 50  # last N transcript entries loaded on resume (TUI-03)


def build_app(campaign_root: Path) -> SagaSmithApp:
    """Open a campaign and return a ready-to-run SagaSmithApp.

    Caller is responsible for ``.run()`` (blocking TUI) or ``.run_test()``
    (async test harness).

    Raises ValueError if the campaign layout is invalid (exits CLI with code 2).
    """
    paths, manifest = open_campaign(campaign_root)
    app = SagaSmithApp(paths=paths, manifest=manifest)

    registry = CommandRegistry()
    registry.register(HelpCommand(registry=registry))
    app.commands = registry  # type: ignore[assignment]

    # Load recent transcript for scrollback (TUI-03).
    app.initial_scrollback = _load_scrollback(paths.db)
    return app


def _load_scrollback(db_path: Path) -> list[str]:
    """Return last SCROLLBACK_LIMIT rendered lines from transcript_entries.

    Rendering rule:
      - kind='player_input'    \u2192 f"> {content}"
      - kind='narration_final' \u2192 content (verbatim)
      - kind='system_note'     \u2192 f"[{content}]"  (T-03-18: unknown kinds also wrap here)

    Uses a read-only connection; closes it before returning.
    """
    lines: list[str] = []
    conn = open_campaign_db(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT kind, content
              FROM transcript_entries
             ORDER BY id DESC
             LIMIT ?
            """,
            (SCROLLBACK_LIMIT,),
        ).fetchall()
    finally:
        conn.close()
    # Rows are newest-first; reverse for chronological display.
    for kind, content in reversed(rows):
        if kind == "player_input":
            lines.append(f"> {content}")
        elif kind == "narration_final":
            lines.append(content)
        else:
            # T-03-18: unknown kinds render as system notes wrapped in [...]
            lines.append(f"[{content}]")
    return lines
