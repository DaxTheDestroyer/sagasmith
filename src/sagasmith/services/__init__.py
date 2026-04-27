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

# SafetyEventService is imported lazily (via __getattr__) to break the circular
# import chain:
#   services.__init__ → safety.py → persistence.repositories → persistence.__init__
#   → app.config → evals.redaction → evals.__init__ → fixtures.py → schemas.__init__
#   → schemas.campaign → services.secrets → services.__init__ (circular)
# Consumers import SafetyEventService directly:
#   from sagasmith.services import SafetyEventService   ← works via __getattr__
#   from sagasmith.services.safety import SafetyEventService  ← also works


def __getattr__(name: str) -> object:  # PEP 562 lazy module attributes
    if name == "SafetyEventService":
        from sagasmith.services.safety import SafetyEventService

        return SafetyEventService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BudgetInspection",
    "BudgetStopError",
    "BudgetStopResult",
    "CostGovernor",
    "CostUpdate",
    "PriceEntry",
    "ProviderCallError",
    # SafetyEventService is available via __getattr__ (lazy load to break circular import).
    # Direct import: `from sagasmith.services.safety import SafetyEventService`
    "SecretRef",
    "SecretRefError",
    "TrustServiceError",
    "compute_degree",
    "estimate_cost_from_usage",
    "load_pricing_table",
    "resolve_secret",
    "scrub_for_log",
]
