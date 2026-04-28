-- Expand turn_records.status CHECK to include narration recovery states.
-- SQLite does not support ALTER CHECK, so the table is recreated.
-- agent_skill_log has FOREIGN KEY (turn_id) REFERENCES turn_records(turn_id),
-- so we temporarily disable FK enforcement during the table swap.

PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS turn_records_new (
    turn_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'needs_vault_repair', 'narrated', 'discarded', 'retried')),
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);

INSERT INTO turn_records_new (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version)
    SELECT turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version FROM turn_records;

DROP TABLE turn_records;
ALTER TABLE turn_records_new RENAME TO turn_records;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;
