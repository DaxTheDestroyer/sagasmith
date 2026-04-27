"""SettingsRepository: typed read/write access to the settings SQLite table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from sagasmith.evals.redaction import RedactionCanary
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.services.errors import TrustServiceError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class SettingsRepository:
    """Typed upsert/get layer over the *settings* SQLite table.

    JSON payloads are scanned by :class:`~sagasmith.evals.redaction.RedactionCanary`
    before every write, mirroring the turn_close.py invariant.  A
    :class:`~sagasmith.services.errors.TrustServiceError` is raised if any
    secret-shaped value is detected, preventing secret material from reaching
    the database.
    """

    conn: sqlite3.Connection

    def put(self, campaign_id: str, key: str, value: BaseModel) -> None:
        """JSON-encode a Pydantic model and upsert into settings.

        Uses ``value.model_dump_json()`` — ``SecretRef.model_dump_json()``
        emits ``{"kind": "env"|"keyring", "name": ..., "account": ...}`` and
        NEVER the resolved secret.  A RedactionCanary scan MUST pass on the
        serialised bytes.
        """
        value_json = value.model_dump_json()
        hits = RedactionCanary().scan(value_json)
        if hits:
            raise TrustServiceError("settings write rejected: secret-shaped payload")
        updated_at = datetime.now(UTC).isoformat()
        self.conn.execute(
            """
            INSERT INTO settings (campaign_id, key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(campaign_id, key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (campaign_id, key, value_json, updated_at),
        )

    def get(self, campaign_id: str, key: str, model: type[T]) -> T | None:
        """Load and validate into *model*, or ``None`` if missing."""
        row = self.conn.execute(
            "SELECT value_json FROM settings WHERE campaign_id = ? AND key = ?",
            (campaign_id, key),
        ).fetchone()
        if row is None:
            return None
        return model.model_validate_json(row[0])

    def get_provider_settings(self, campaign_id: str) -> ProviderSettings | None:
        """Convenience wrapper to load the ``provider`` settings key."""
        return self.get(campaign_id, "provider", ProviderSettings)

    def put_provider_settings(self, campaign_id: str, settings: ProviderSettings) -> None:
        """Convenience wrapper to persist *settings* under the ``provider`` key."""
        self.put(campaign_id, "provider", settings)
