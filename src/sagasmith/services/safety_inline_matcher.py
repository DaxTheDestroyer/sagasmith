"""SafetyInlineMatcher Adapter over the Safety Guard Module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.safety_guard import SafetyGuard

MatchKind = Literal["hard_limit"]


@dataclass(frozen=True)
class InlineMatch:
    """Result of a hard-limit pattern hit during streaming."""

    kind: MatchKind
    term: str
    matched_text: str


@dataclass(frozen=True)
class SafetyInlineMatcher:
    """Legacy hard-limit stream scanner Adapter."""

    _guard: SafetyGuard

    def __init__(self, policy: Any | None = None) -> None:
        object.__setattr__(self, "_guard", SafetyGuard(policy))

    def match(self, buffer: str) -> InlineMatch | None:
        """Return first hard-limit hit in buffer, or None if clean."""

        hit = self._guard.check_stream(buffer)
        if hit is None:
            return None
        return InlineMatch(kind=hit.kind, term=hit.term, matched_text=hit.matched_text)


__all__ = ["InlineMatch", "MatchKind", "SafetyInlineMatcher"]
