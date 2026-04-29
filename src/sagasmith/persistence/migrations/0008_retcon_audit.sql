-- Migration 0008: retain retconned turn audit metadata and vault write impact rows.

PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS turn_records_new (
    turn_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'needs_vault_repair', 'narrated', 'discarded', 'retried', 'retconned')),
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    sync_warning TEXT
);

INSERT INTO turn_records_new (
    turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version, sync_warning
)
    SELECT turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version, sync_warning FROM turn_records;

DROP TABLE turn_records;
ALTER TABLE turn_records_new RENAME TO turn_records;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS retcon_audit (
    retcon_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    selected_turn_id TEXT NOT NULL,
    affected_turn_ids_json TEXT NOT NULL,
    prior_checkpoint_id TEXT NOT NULL,
    confirmation_token TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retcon_audit_campaign_created ON retcon_audit(campaign_id, created_at);

CREATE TABLE IF NOT EXISTS vault_write_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    vault_path TEXT NOT NULL,
    operation TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vault_write_audit_turn ON vault_write_audit(turn_id, id);
