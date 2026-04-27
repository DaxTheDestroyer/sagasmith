CREATE TABLE IF NOT EXISTS safety_events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    turn_id TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('pause', 'line', 'soft_limit_fade', 'post_gate_rewrite', 'fallback')),
    policy_ref TEXT,
    action_taken TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'player_visible' CHECK (visibility IN ('player_visible')),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE INDEX IF NOT EXISTS idx_safety_events_campaign ON safety_events(campaign_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_safety_events_turn ON safety_events(turn_id);
