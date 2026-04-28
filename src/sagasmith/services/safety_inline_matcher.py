"""SafetyInlineMatcher — cheap regex/keyword scanner over ContentPolicy hard limits.

D-06.1: Designed to run on every accumulated token window during streaming
without measurable latency.  Compiled once at init time.  Used by the Orator
to short-circuit doomed generations before paying for full output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from sagasmith.schemas.player import ContentPolicy

MatchKind = Literal["hard_limit"]


@dataclass(frozen=True)
class InlineMatch:
    """Result of a hard-limit pattern hit during streaming."""

    kind: MatchKind
    term: str
    matched_text: str


# Shared synonym tables with safety_post_gate and safety_pre_gate
_HARDSYN: dict[str, tuple[str, ...]] = {
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

_HARD_LOOSE: dict[str, tuple[str, ...]] = {
    "harm_to_children": (r"child.{0,30}harm", r"harm.{0,30}child"),
}


def _compile_hard_patterns(
    terms: list[str],
) -> list[tuple[str, re.Pattern[str]]]:
    """Compile hard-limit terms into (canonical_term, compiled_regex) pairs."""
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        synonyms = (term, term.replace("_", " "), *_HARDSYN.get(term, ()))
        escaped = [re.escape(s) for s in synonyms if s]
        if escaped:
            combined = "|".join(escaped)
            patterns.append((term, re.compile(rf"\b(?:{combined})\b", re.IGNORECASE)))
        for loose_pattern in _HARD_LOOSE.get(term, ()):
            patterns.append((term, re.compile(loose_pattern, re.IGNORECASE)))
    return patterns


@dataclass(frozen=True)
class SafetyInlineMatcher:
    """Cheap regex scanner over ContentPolicy hard_limits.

    Usage::

        matcher = SafetyInlineMatcher(policy)
        hit = matcher.match(buffer_text)
        if hit is not None:
            # cancel stream, trigger rewrite
    """

    _patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)

    def __init__(self, policy: ContentPolicy | dict | None = None) -> None:
        if policy is None:
            object.__setattr__(self, "_patterns", [])
            return
        cp = ContentPolicy.model_validate(policy) if isinstance(policy, dict) else policy
        object.__setattr__(self, "_patterns", _compile_hard_patterns(cp.hard_limits))

    def match(self, buffer: str) -> InlineMatch | None:
        """Return first hard-limit hit in ``buffer``, or None if clean."""
        for term, pattern in self._patterns:
            m = pattern.search(buffer)
            if m is not None:
                return InlineMatch(
                    kind="hard_limit",
                    term=term,
                    matched_text=m.group(0),
                )
        return None
