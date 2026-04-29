"""SafetyPreGate — pre-generation content-policy gate using compiled keyword/regex patterns.

D-06.3: Pre-gate returns a routing verdict (Allowed / Rerouted / Blocked),
never raises an exception.  The Oracle node — not this service — posts
``InterruptKind.SAFETY_BLOCK`` when it receives a ``Blocked`` verdict.

Follows the ``RedactionCanary`` frozen-dataclass pattern: patterns are compiled
once at ``__init__`` time and the check method is a pure function.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from sagasmith.schemas.player import ContentPolicy

# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

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
    """Intent matched a soft or hard limit — use the substituted ``intent``."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("rerouted", intent, reason, policy_ref)


class Blocked(PreGateVerdict):
    """Intent blocked — halt and post SAFETY_BLOCK interrupt."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("blocked", intent, reason, policy_ref)


# ---------------------------------------------------------------------------
# Compiled pattern helpers
# ---------------------------------------------------------------------------

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


def _compile_limit_patterns(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    """Compile a list of policy terms into (canonical_term, compiled_regex) pairs."""
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        synonyms = (term, term.replace("_", " "), *_POLICY_SYNONYMS.get(term, ()))
        escaped = [re.escape(s) for s in synonyms if s]
        if escaped:
            combined = "|".join(escaped)
            patterns.append((term, re.compile(rf"\b(?:{combined})\b", re.IGNORECASE)))
        # Loose regex patterns for co-occurrence detection (no word-boundary wrapper)
        loose = list(_REGEX_SYNONYMS.get(term, ()))
        if loose:
            combined_loose = "|".join(loose)
            patterns.append((term, re.compile(combined_loose, re.IGNORECASE)))
    return patterns


def _redact_text(text: str, term: str) -> str:
    """Replace all matches of a policy term (and synonyms) with a safe substitute."""
    replacement = "safety-aware offscreen complication"
    synonyms = (term, term.replace("_", " "), *_POLICY_SYNONYMS.get(term, ()))
    result = text
    for syn in synonyms:
        if syn:
            result = re.sub(re.escape(syn), replacement, result, flags=re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# SafetyPreGate service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyPreGate:
    """Pre-generation safety gate with compiled keyword/regex patterns.

    Usage::

        gate = SafetyPreGate(policy)
        verdict = gate.check("scene intent text")
    """

    _hard_limit_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    _soft_limit_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    _soft_limit_actions: dict[str, str] = field(default_factory=dict)

    def __init__(self, policy: ContentPolicy | dict[str, Any] | None = None) -> None:
        if policy is None:
            object.__setattr__(self, "_hard_limit_patterns", [])
            object.__setattr__(self, "_soft_limit_patterns", [])
            object.__setattr__(self, "_soft_limit_actions", {})
            return

        cp = ContentPolicy.model_validate(policy) if isinstance(policy, dict) else policy
        object.__setattr__(self, "_hard_limit_patterns", _compile_limit_patterns(cp.hard_limits))
        object.__setattr__(
            self,
            "_soft_limit_patterns",
            _compile_limit_patterns(list(cp.soft_limits.keys())),
        )
        object.__setattr__(self, "_soft_limit_actions", dict(cp.soft_limits))

    def check(self, intent: str) -> PreGateVerdict:
        """Check ``intent`` against compiled hard and soft limits.

        Returns ``Allowed``, ``Rerouted``, or ``Blocked`` — never raises.
        """
        text = intent.strip()
        lowered = text.lower()

        # --- Hard limits ---
        for term, pattern in self._hard_limit_patterns:
            if not pattern.search(lowered):
                continue
            # If the intent IS the policy term itself, block outright
            if lowered in {term.lower(), term.replace("_", " ").lower()}:
                return Blocked(text, reason=f"hard limit blocked: {term}", policy_ref=term)
            # Try redaction-based reroute
            safe = _redact_text(text, term)
            if safe != text:
                return Rerouted(safe, reason=f"hard limit rerouted: {term}", policy_ref=term)
            # Couldn't redact — block
            return Blocked(text, reason=f"hard limit blocked: {term}", policy_ref=term)

        # --- Soft limits ---
        warnings: list[str] = []
        routed = text
        for term, pattern in self._soft_limit_patterns:
            if not pattern.search(lowered):
                continue
            action = self._soft_limit_actions.get(term, "fade_to_black")
            warnings.append(f"{term}:{action}")
            if action == "ask_first":
                return Blocked(
                    text,
                    reason=f"needs_player_consent: {term}",
                    policy_ref=term,
                )
            # fade_to_black or avoid_detail → redact and reroute
            routed = _redact_text(routed, term)

        if routed != text:
            return Rerouted(
                routed, reason="soft limit adjusted", policy_ref=warnings[0] if warnings else None
            )

        return Allowed(text, content_warnings=tuple(warnings))
