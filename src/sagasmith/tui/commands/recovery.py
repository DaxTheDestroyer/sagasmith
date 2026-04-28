"""Recovery command implementations: retry (/retry) and discard (/discard).

These commands allow the player to recover from incomplete narration:
- /retry   — re-runs Orator + Archivist from the pre-narration checkpoint
- /discard — discards the incomplete turn entirely, rewinding to pre-narration state

Both are disabled when no incomplete narration exists (i.e., the graph is not
paused at the orator interrupt).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp

from sagasmith.tui.widgets.narration import NarrationArea


def _write(app: SagaSmithApp, line: str) -> None:
    app.query_one(NarrationArea).append_line(line)


def _has_incomplete_narration(app: SagaSmithApp) -> bool:
    """Return True if the graph is paused at the orator interrupt for the current turn."""
    if app.graph_runtime is None or app.current_turn_id is None:
        return False
    snapshot = app.graph_runtime.graph.get_state(app.graph_runtime.thread_config)
    values = getattr(snapshot, "values", {}) or {}
    return (
        snapshot.next == ("orator",)
        and values.get("turn_id") == app.current_turn_id
    )


@dataclass(frozen=True)
class RetryCommand:
    name: str = "retry"
    description: str = "Re-run narration from pre-narration checkpoint."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        if not _has_incomplete_narration(app):
            _write(app, "[system] /retry: no incomplete narration to retry.")
            return
        turn_id = app.current_turn_id
        assert turn_id is not None  # guarded above
        try:
            result = app.graph_runtime.retry_narration(turn_id)
        except ValueError as exc:
            _write(app, f"[system] /retry failed: {exc}")
            return
        # Sync new narration from the retried turn.
        app._sync_narration_from_graph()
        pending = result.get("pending_narration", [])
        if pending:
            _write(app, f"[system] Narration retried ({len(pending)} lines).")


@dataclass(frozen=True)
class DiscardCommand:
    name: str = "discard"
    description: str = "Discard incomplete narration and rewind to pre-narration state."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        if not _has_incomplete_narration(app):
            _write(app, "[system] /discard: no incomplete narration to discard.")
            return
        turn_id = app.current_turn_id
        assert turn_id is not None  # guarded above
        try:
            result = app.graph_runtime.discard_incomplete_turn(turn_id)
        except ValueError as exc:
            _write(app, f"[system] /discard failed: {exc}")
            return
        _write(app, f"[system] Turn {turn_id} discarded (status={result.status}).")
