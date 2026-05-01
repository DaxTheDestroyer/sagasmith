"""Application bootstrap, config, session identity, and dependency wiring."""

from sagasmith.app.campaign_ref import OpenedCampaign, open_campaign_ref
from sagasmith.app.config import SettingsRepository
from sagasmith.app.paths import CampaignPaths, resolve_campaign_paths, validate_campaign_paths

__all__ = [
    "CampaignPaths",
    "OpenedCampaign",
    "SettingsRepository",
    "open_campaign_ref",
    "resolve_campaign_paths",
    "validate_campaign_paths",
]
