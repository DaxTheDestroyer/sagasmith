"""Graph interrupt envelopes + canary guard.

Interrupts use LangGraph's native update_state + Command(resume=...) pattern:
- `post_interrupt` writes an envelope to state via `graph.update_state`.
- `resume_after_interrupt` clears it and resumes the thread.

This is NOT a shadow mechanism — it's the documented LangGraph API for
passing caller-side signals through to graph execution. See 04-REVIEWS.md
consensus change #1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sagasmith.services.errors import TrustServiceError


class InterruptKind(StrEnum):
    PAUSE = "pause"
    LINE = "line"
    RETCON = "retcon"      # defined but not posted in Phase 4 — Phase 8 scope
    BUDGET_STOP = "budget_stop"
    SESSION_END = "session_end"


@dataclass(frozen=True)
class InterruptEnvelope:
    kind: InterruptKind
    payload: dict[str, Any]
    thread_id: str
    created_at: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "payload": self.payload,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
        }

    @classmethod
    def build(cls, *, kind: InterruptKind, payload: dict[str, Any] | None, thread_id: str, canary: Any = None) -> InterruptEnvelope:
        payload = payload or {}
        # Redaction canary guard
        if canary is None:
            from sagasmith.evals.redaction import RedactionCanary
            canary = RedactionCanary()
        import json
        if canary.scan(json.dumps(payload)):
            raise TrustServiceError(f"interrupt payload for kind={kind} contains redacted content")
        return cls(
            kind=kind,
            payload=payload,
            thread_id=thread_id,
            created_at=datetime.now(UTC).isoformat(),
        )


def extract_pending_interrupt(runtime) -> dict[str, Any] | None:
    """Inspect the runtime's current graph state for a pending interrupt envelope."""
    snapshot = runtime.graph.get_state(runtime.thread_config)
    values = getattr(snapshot, "values", {}) or {}
    return values.get("last_interrupt")
