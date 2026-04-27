"""Deterministic trust services: secrets, cost, dice, PF2e math."""

from sagasmith.services.cost import (
    BudgetInspection,
    BudgetStopResult,
    CostGovernor,
    CostUpdate,
)
from sagasmith.services.errors import (
    BudgetStopError,
    ProviderCallError,
    SecretRefError,
    TrustServiceError,
)
from sagasmith.services.pf2e import compute_degree
from sagasmith.services.pricing_table import (
    PriceEntry,
    estimate_cost_from_usage,
    load_pricing_table,
)
from sagasmith.services.secrets import SecretRef, resolve_secret, scrub_for_log

__all__ = [
    "BudgetInspection",
    "BudgetStopError",
    "BudgetStopResult",
    "CostGovernor",
    "CostUpdate",
    "PriceEntry",
    "ProviderCallError",
    "SecretRef",
    "SecretRefError",
    "TrustServiceError",
    "compute_degree",
    "estimate_cost_from_usage",
    "load_pricing_table",
    "resolve_secret",
    "scrub_for_log",
]
