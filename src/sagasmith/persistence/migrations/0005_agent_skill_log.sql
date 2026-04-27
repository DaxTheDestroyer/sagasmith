CREATE TABLE IF NOT EXISTS agent_skill_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    agent_name TEXT NOT NULL CHECK (agent_name IN ('onboarding','oracle','rules_lawyer','orator','archivist')),
    skill_name TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('success','interrupted','error')),
    FOREIGN KEY (turn_id) REFERENCES turn_records(turn_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_log_turn ON agent_skill_log(turn_id);
CREATE INDEX IF NOT EXISTS idx_agent_log_agent ON agent_skill_log(agent_name, started_at);
