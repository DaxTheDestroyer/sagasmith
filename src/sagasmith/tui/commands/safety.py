"""Safety command implementations: pause (/pause) and line (/line)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp

from sagasmith.services.errors import TrustServiceError
from sagasmith.tui.widgets.narration import NarrationArea


def _write(app: SagaSmithApp, line: str) -> None:
    app.query_one(NarrationArea).append_line(line)


@dataclass(frozen=True)
class PauseCommand:
    name: str = "pause"
    description: str = "Pause play — captured as a persisted safety event (SAFE-04)."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        # Preserve Phase 3 SafetyEvent write
        service = app.safety_events
        if service is None:
            _write(app, "[SAFETY] Paused. (No campaign bound — event not persisted.)")
            return
        try:
            record = service.log_pause(campaign_id=app.manifest.campaign_id, turn_id=None)
        except TrustServiceError as exc:
            _write(app, f"[SAFETY] /pause failed: {exc}")
            return
        # Phase 4: post graph interrupt if runtime bound
        if app.graph_runtime is not None:
            from sagasmith.graph.interrupts import InterruptKind

            app.graph_runtime.post_interrupt(
                kind=InterruptKind.PAUSE,
                payload={"reason": "player typed /pause"},
            )
        _write(app, f"[SAFETY] Paused. (event {record.event_id})")


@dataclass(frozen=True)
class LineCommand:
    name: str = "line"
    description: str = "Redline a topic; Orator routes around it (SAFE-05)."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        if not args:
            _write(app, "[SAFETY] /line requires a topic. Usage: /line <topic>")
            return
        topic = " ".join(args)
        service = app.safety_events
        if service is None:
            _write(app, f"[SAFETY] Line drawn: {topic}. (No campaign bound — event not persisted.)")
            return
        try:
            record = service.log_line(
                campaign_id=app.manifest.campaign_id, topic=topic, turn_id=None
            )
        except ValueError as exc:
            _write(app, f"[SAFETY] /line error: {exc}")
            return
        except TrustServiceError as exc:
            _write(app, f"[SAFETY] /line rejected: {exc}")
            return
        # Phase 4: post graph interrupt if runtime bound
        if app.graph_runtime is not None:
            from sagasmith.graph.interrupts import InterruptKind

            app.graph_runtime.post_interrupt(
                kind=InterruptKind.LINE,
                payload={"topic": topic},
            )
        _write(
            app,
            f"[SAFETY] Line drawn: {topic}. Orator will route around this topic. (event {record.event_id})",
        )
