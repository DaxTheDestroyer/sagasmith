"""SafetyPostGate Adapter over the Safety Guard Module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.providers.client import LLMClient
from sagasmith.safety_guard import GeneratedFallback, GeneratedRewrite, SafetyGuard

PostVerdictKind = Literal["pass", "rewrite", "block_fallback"]


@dataclass(frozen=True)
class PostGateVerdict:
    """Result of a post-generation safety scan."""

    kind: PostVerdictKind
    reason: str | None = None
    violated_term: str | None = None
    redacted_prose: str | None = None


class Pass(PostGateVerdict):
    """Prose passed all checks."""

    def __init__(self) -> None:
        super().__init__("pass")


class Rewrite(PostGateVerdict):
    """Prose needs rewriting — soft-limit or borderline content detected."""

    def __init__(
        self, *, reason: str, violated_term: str, redacted_prose: str | None = None
    ) -> None:
        super().__init__("rewrite", reason, violated_term, redacted_prose)


class BlockFallback(PostGateVerdict):
    """Prose blocked — use fallback narration."""

    def __init__(self, *, reason: str, violated_term: str) -> None:
        super().__init__("block_fallback", reason, violated_term)


@dataclass(frozen=True)
class SafetyPostGate:
    """Legacy post-generation safety gate Adapter."""

    llm_client: LLMClient | None
    cheap_model: str

    def scan(
        self,
        prose: str,
        policy: Any | None = None,
    ) -> PostGateVerdict:
        """Scan prose against content policy and return the legacy verdict shape."""

        decision = SafetyGuard(
            policy,
            llm_client=self.llm_client,
            cheap_model=self.cheap_model,
        ).scan_generated_prose(prose)
        if isinstance(decision, GeneratedFallback):
            return BlockFallback(
                reason=decision.reason or "blocked",
                violated_term=decision.violated_term or "unknown",
            )
        if isinstance(decision, GeneratedRewrite):
            return Rewrite(
                reason=decision.reason or "rewrite",
                violated_term=decision.violated_term or "unknown",
                redacted_prose=decision.redacted_prose,
            )
        return Pass()


__all__ = [
    "BlockFallback",
    "Pass",
    "PostGateVerdict",
    "PostVerdictKind",
    "Rewrite",
    "SafetyPostGate",
]
