"""SQLite persistence package for trust-records, migrations, and turn-close."""

from sagasmith.app.config import SettingsRepository
from sagasmith.persistence.db import campaign_db, current_schema_version, open_campaign_db
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import (
    CheckpointRefRepository,
    CostLogRepository,
    ProviderLogRepository,
    RollLogRepository,
    StateDeltaRepository,
    TranscriptRepository,
    TurnRecordRepository,
)
from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn

__all__ = [
    "CheckpointRefRepository",
    "CostLogRepository",
    "ProviderLogRepository",
    "RollLogRepository",
    "SettingsRepository",
    "StateDeltaRepository",
    "TranscriptRepository",
    "TurnCloseBundle",
    "TurnRecordRepository",
    "apply_migrations",
    "campaign_db",
    "close_turn",
    "current_schema_version",
    "open_campaign_db",
]
