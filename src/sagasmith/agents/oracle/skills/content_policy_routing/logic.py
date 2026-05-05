"""Content-policy routing Adapter for Oracle scene intents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.safety_guard import IntentBlocked, IntentRerouted, SafetyGuard
from sagasmith.schemas.player import ContentPolicy

RouteKind = Literal["allowed", "rerouted", "blocked"]


@dataclass(frozen=True)
class PolicyRouteResult:
    kind: RouteKind
    intent: str
    reason: str | None = None
    policy_ref: str | None = None
    content_warnings: tuple[str, ...] = ()


class Allowed(PolicyRouteResult):
    def __init__(self, intent: str, *, content_warnings: tuple[str, ...] = ()) -> None:
        super().__init__("allowed", intent, None, None, content_warnings)


class Rerouted(PolicyRouteResult):
    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("rerouted", intent, reason, policy_ref, ())


class Blocked(PolicyRouteResult):
    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("blocked", intent, reason, policy_ref, ())


def route_scene_intent(
    *,
    scene_intent: str,
    content_policy: ContentPolicy | dict[str, Any] | None,
) -> PolicyRouteResult:
    """Apply deterministic pre-generation policy routing to a scene intent."""

    decision = SafetyGuard(content_policy).route_intent(scene_intent)
    if isinstance(decision, IntentBlocked):
        return Blocked(
            decision.intent,
            reason=_skill_reason(decision.reason, "blocked before generation"),
            policy_ref=decision.policy_ref or "",
        )
    if isinstance(decision, IntentRerouted):
        return Rerouted(
            decision.intent,
            reason=_skill_reason(decision.reason, "rerouted before generation"),
            policy_ref=decision.policy_ref or "",
        )
    return Allowed(decision.intent, content_warnings=decision.content_warnings)


def safety_pre_gate(
    intent: str, content_policy: ContentPolicy | dict[str, Any] | None
) -> PolicyRouteResult:
    """D-06.3-compatible pre-gate facade for Oracle."""

    return route_scene_intent(scene_intent=intent, content_policy=content_policy)


def _skill_reason(reason: str | None, suffix: str) -> str:
    if reason is None:
        return suffix
    if reason.startswith("hard limit blocked:"):
        return reason.replace("hard limit blocked:", "hard limit blocked before generation:")
    if reason.startswith("hard limit rerouted:"):
        return reason.replace("hard limit rerouted:", "hard limit rerouted before generation:")
    if reason == "soft limit adjusted":
        return "soft limit adjusted before generation"
    return reason


__all__ = [
    "Allowed",
    "Blocked",
    "PolicyRouteResult",
    "Rerouted",
    "RouteKind",
    "route_scene_intent",
    "safety_pre_gate",
]
