CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turn_records (
    turn_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'needs_vault_repair')),
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('player_input', 'narration_final', 'system_note')),
    content TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transcript_turn ON transcript_entries(turn_id, sequence);

CREATE TABLE IF NOT EXISTS roll_logs (
    roll_id TEXT PRIMARY KEY,
    turn_id TEXT,
    seed TEXT NOT NULL,
    die TEXT NOT NULL,
    natural INTEGER NOT NULL,
    modifier INTEGER NOT NULL,
    total INTEGER NOT NULL,
    dc INTEGER,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_roll_turn ON roll_logs(turn_id);

CREATE TABLE IF NOT EXISTS provider_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('openrouter', 'fake')),
    model TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    turn_id TEXT,
    provider_response_id TEXT,
    failure_kind TEXT NOT NULL,
    retry_count INTEGER NOT NULL CHECK (retry_count >= 0),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cached_prompt_tokens INTEGER,
    provider_cost_usd REAL,
    cost_estimate_usd REAL,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    safe_snippet TEXT,
    response_hash TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_turn ON provider_logs(turn_id);
CREATE INDEX IF NOT EXISTS idx_provider_request ON provider_logs(request_id);

CREATE TABLE IF NOT EXISTS cost_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    cost_usd REAL NOT NULL CHECK (cost_usd >= 0),
    cost_is_approximate INTEGER NOT NULL CHECK (cost_is_approximate IN (0, 1)),
    tokens_prompt INTEGER NOT NULL,
    tokens_completion INTEGER NOT NULL,
    warnings_fired_json TEXT NOT NULL,
    spent_usd_after REAL NOT NULL CHECK (spent_usd_after >= 0),
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_turn ON cost_logs(turn_id);

CREATE TABLE IF NOT EXISTS state_deltas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    delta_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('rules', 'oracle', 'archivist', 'safety', 'user')),
    path TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('set', 'increment', 'append', 'remove')),
    value_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delta_turn ON state_deltas(turn_id);

CREATE TABLE IF NOT EXISTS checkpoint_refs (
    checkpoint_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pre_narration', 'final')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoint_turn ON checkpoint_refs(turn_id);
