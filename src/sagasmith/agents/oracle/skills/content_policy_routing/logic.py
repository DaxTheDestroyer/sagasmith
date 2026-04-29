"""Content-policy routing logic for Oracle scene intents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

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


_POLICY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "graphic_sexual_content": ("sexual assault", "explicit sex", "graphic sexual"),
    "harm_to_children": (
        "harm a child",
        "children are harmed",
        "child corpse",
        "injured child",
        "child harmed",
        "harmed child",
        "children harmed",
        "harming children",
    ),
    "graphic_violence": ("gore", "dismember", "graphic violence", "viscera"),
}

_REGEX_SYNONYMS: dict[str, tuple[str, ...]] = {
    "harm_to_children": (r"child.{0,30}harm", r"harm.{0,30}child"),
}


def route_scene_intent(
    *,
    scene_intent: str,
    content_policy: ContentPolicy | dict[str, Any] | None,
) -> PolicyRouteResult:
    """Apply deterministic pre-generation policy routing to a scene intent."""

    if content_policy is None:
        return Allowed(scene_intent)
    policy = ContentPolicy.model_validate(content_policy)
    text = scene_intent.strip()
    lowered = text.lower()
    for hard_limit in policy.hard_limits:
        if _matches_policy_term(lowered, hard_limit):
            if lowered in {hard_limit.lower(), hard_limit.replace("_", " ").lower()}:
                return Blocked(
                    text,
                    reason=f"hard limit blocked before generation: {hard_limit}",
                    policy_ref=hard_limit,
                )
            safe_intent = _redact_term(text, hard_limit)
            if safe_intent != text:
                return Rerouted(
                    safe_intent,
                    reason=f"hard limit rerouted before generation: {hard_limit}",
                    policy_ref=hard_limit,
                )
            return Blocked(
                text,
                reason=f"hard limit blocked before generation: {hard_limit}",
                policy_ref=hard_limit,
            )
    warnings: list[str] = []
    routed_text = text
    for soft_limit, action in policy.soft_limits.items():
        if _matches_policy_term(lowered, soft_limit):
            warnings.append(f"{soft_limit}:{action}")
            routed_text = _redact_term(routed_text, soft_limit)
    if routed_text != text:
        return Rerouted(
            routed_text,
            reason="soft limit adjusted before generation",
            policy_ref=warnings[0] if warnings else None,
        )
    return Allowed(text, content_warnings=tuple(warnings))


def safety_pre_gate(
    intent: str, content_policy: ContentPolicy | dict[str, Any] | None
) -> PolicyRouteResult:
    """D-06.3-compatible pre-gate facade for Oracle."""

    return route_scene_intent(scene_intent=intent, content_policy=content_policy)


def _matches_policy_term(text: str, policy_term: str) -> bool:
    normalized = policy_term.replace("_", " ").lower()
    terms = (normalized, policy_term.lower(), *_POLICY_SYNONYMS.get(policy_term, ()))
    if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms if term):
        return True
    for loose in _REGEX_SYNONYMS.get(policy_term, ()):
        if re.search(loose, text, re.IGNORECASE):
            return True
    return False


def _redact_term(text: str, policy_term: str) -> str:
    replacement = "safety-aware offscreen complication"
    routed = text
    for term in (
        policy_term,
        policy_term.replace("_", " "),
        *_POLICY_SYNONYMS.get(policy_term, ()),
    ):
        routed = re.sub(re.escape(term), replacement, routed, flags=re.IGNORECASE)
    return routed
