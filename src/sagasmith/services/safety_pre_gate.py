"""SafetyPreGate Adapter over the Safety Guard Module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.safety_guard import IntentBlocked, IntentRerouted, SafetyGuard

VerdictKind = Literal["allowed", "rerouted", "blocked"]


@dataclass(frozen=True)
class PreGateVerdict:
    """Base verdict from the safety pre-gate."""

    kind: VerdictKind
    intent: str
    reason: str | None = None
    policy_ref: str | None = None
    content_warnings: tuple[str, ...] = ()


class Allowed(PreGateVerdict):
    """Intent passed all gates — proceed unchanged."""

    def __init__(self, intent: str, *, content_warnings: tuple[str, ...] = ()) -> None:
        super().__init__("allowed", intent, None, None, content_warnings)


class Rerouted(PreGateVerdict):
    """Intent matched a soft or hard limit — use the substituted intent."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("rerouted", intent, reason, policy_ref)


class Blocked(PreGateVerdict):
    """Intent blocked — halt and post SAFETY_BLOCK interrupt."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("blocked", intent, reason, policy_ref)


@dataclass(frozen=True)
class SafetyPreGate:
    """Legacy pre-generation safety gate Adapter."""

    _guard: SafetyGuard

    def __init__(self, policy: Any | None = None) -> None:
        object.__setattr__(self, "_guard", SafetyGuard(policy))

    def check(self, intent: str) -> PreGateVerdict:
        """Check intent against content policy and return the legacy verdict shape."""

        decision = self._guard.route_intent(intent)
        if isinstance(decision, IntentBlocked):
            return Blocked(
                decision.intent,
                reason=decision.reason or "blocked",
                policy_ref=decision.policy_ref or "",
            )
        if isinstance(decision, IntentRerouted):
            return Rerouted(
                decision.intent,
                reason=decision.reason or "rerouted",
                policy_ref=decision.policy_ref or "",
            )
        return Allowed(decision.intent, content_warnings=decision.content_warnings)


__all__ = ["Allowed", "Blocked", "PreGateVerdict", "Rerouted", "SafetyPreGate", "VerdictKind"]
