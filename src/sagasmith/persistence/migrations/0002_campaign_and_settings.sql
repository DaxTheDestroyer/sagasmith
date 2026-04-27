CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    campaign_name TEXT NOT NULL,
    campaign_slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sagasmith_version TEXT NOT NULL,
    manifest_version INTEGER NOT NULL CHECK (manifest_version = 1)
);

CREATE TABLE IF NOT EXISTS settings (
    campaign_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (campaign_id, key),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
