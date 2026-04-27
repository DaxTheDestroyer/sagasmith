"""SafetyEventService — persist and read-back player-visible safety events.

RedactionCanary is imported lazily inside _log to break the circular import:
  services.__init__ → services.safety → evals.redaction → evals.__init__ →
  evals.fixtures → schemas.__init__ → schemas.campaign → services.__init__
"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sagasmith.persistence.repositories import SafetyEventRepository
from sagasmith.schemas.persistence import SafetyEventRecord
from sagasmith.services.errors import TrustServiceError

if TYPE_CHECKING:
    pass  # RedactionCanary referenced via _canary: Any at runtime


def _event_id() -> str:
    return f"safety_{secrets.token_hex(6)}"


def _default_canary() -> Any:
    """Lazy factory for RedactionCanary — defers package init to first use."""
    from sagasmith.evals.redaction import RedactionCanary as _RC

    return _RC()


@dataclass(frozen=True)
class SafetyEventService:
    """Persist and read-back player-visible safety events.

    All writes pass RedactionCanary — no secrets can be stored in action_taken
    or policy_ref strings. Plan 03-04 events never carry GM-only content
    (SAFE-06); the table's visibility CHECK constraint enforces this at schema level.

    Note: _canary is typed Any to break circular import at module load time.
    At runtime it will always be a RedactionCanary instance. See _default_canary().
    """

    conn: sqlite3.Connection
    _canary: Any = field(default_factory=_default_canary)

    def log_pause(self, *, campaign_id: str, turn_id: str | None = None) -> SafetyEventRecord:
        return self._log(
            campaign_id=campaign_id,
            turn_id=turn_id,
            kind="pause",
            policy_ref=None,
            action_taken="player requested pause",
        )

    def log_line(
        self,
        *,
        campaign_id: str,
        topic: str,
        turn_id: str | None = None,
    ) -> SafetyEventRecord:
        topic_clean = topic.strip()
        if not topic_clean:
            raise ValueError("/line requires a topic")
        if len(topic_clean) > 200:
            raise ValueError("/line topic too long (max 200 chars)")
        return self._log(
            campaign_id=campaign_id,
            turn_id=turn_id,
            kind="line",
            policy_ref=topic_clean,
            action_taken=f"redlined:{topic_clean}",
        )

    def log_fallback(
        self,
        *,
        campaign_id: str,
        reason: str,
        turn_id: str | None = None,
    ) -> SafetyEventRecord:
        """Reserved for Phase 6 SafetyGuard post-gate fallback. Exposed now so
        the service surface is stable when Phase 6 lands."""
        return self._log(
            campaign_id=campaign_id,
            turn_id=turn_id,
            kind="fallback",
            policy_ref=None,
            action_taken=f"fallback:{reason[:200]}",
        )

    def list_recent(self, campaign_id: str, *, limit: int = 20) -> list[SafetyEventRecord]:
        return SafetyEventRepository(self.conn).list_for_campaign(campaign_id, limit=limit)

    def _log(self, **kwargs: object) -> SafetyEventRecord:
        record = SafetyEventRecord(
            event_id=_event_id(),
            timestamp=datetime.now(UTC).isoformat(),
            **kwargs,  # type: ignore[arg-type]
        )
        # SAFE-06: redaction invariant
        payload = record.model_dump_json()
        hits = self._canary.scan(payload)
        if hits:
            raise TrustServiceError(
                f"safety event rejected by redaction canary: label={hits[0].label}"
            )
        with self.conn:  # atomic
            SafetyEventRepository(self.conn).append(record)
        return record
