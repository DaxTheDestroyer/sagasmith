CREATE TABLE IF NOT EXISTS onboarding_player_profile (
    campaign_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS onboarding_content_policy (
    campaign_id TEXT PRIMARY KEY,
    policy_json TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS onboarding_house_rules (
    campaign_id TEXT PRIMARY KEY,
    rules_json TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);
