"""Safety Guard: shared content-policy matching and narration safety decisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from sagasmith.providers.client import LLMClient
from sagasmith.schemas.player import ContentPolicy
from sagasmith.schemas.provider import LLMRequest, Message
from sagasmith.schemas.safety_cost import SafetyEvent

DEFAULT_FALLBACK_NARRATION = "The scene shifts. A new detail draws your attention."
DEFAULT_MAX_REWRITES = 2
_SAFE_REPLACEMENT = "safety-aware offscreen complication"


IntentDecisionKind = Literal["allowed", "rerouted", "blocked"]
GeneratedDecisionKind = Literal["pass", "rewrite", "fallback"]
RetryAction = Literal["continue", "retry", "fallback"]


@dataclass(frozen=True)
class IntentDecision:
    """Pre-generation content-policy routing decision."""

    kind: IntentDecisionKind
    intent: str
    reason: str | None = None
    policy_ref: str | None = None
    content_warnings: tuple[str, ...] = ()


class IntentAllowed(IntentDecision):
    """Scene intent is safe to use unchanged."""

    def __init__(self, intent: str, *, content_warnings: tuple[str, ...] = ()) -> None:
        super().__init__("allowed", intent, None, None, content_warnings)


class IntentRerouted(IntentDecision):
    """Scene intent was rewritten to avoid configured content."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("rerouted", intent, reason, policy_ref, ())


class IntentBlocked(IntentDecision):
    """Scene intent must not proceed to generation."""

    def __init__(self, intent: str, *, reason: str, policy_ref: str) -> None:
        super().__init__("blocked", intent, reason, policy_ref, ())


@dataclass(frozen=True)
class StreamHit:
    """Hard-limit match found while buffering streamed prose."""

    kind: Literal["hard_limit"]
    term: str
    matched_text: str


@dataclass(frozen=True)
class GeneratedProseDecision:
    """Post-generation decision for completed narration prose."""

    kind: GeneratedDecisionKind
    reason: str | None = None
    violated_term: str | None = None
    redacted_prose: str | None = None


class GeneratedAllowed(GeneratedProseDecision):
    """Generated prose passed safety checks."""

    def __init__(self) -> None:
        super().__init__("pass")


class GeneratedRewrite(GeneratedProseDecision):
    """Generated prose should be retried or rewritten."""

    def __init__(
        self, *, reason: str, violated_term: str, redacted_prose: str | None = None
    ) -> None:
        super().__init__("rewrite", reason, violated_term, redacted_prose)


class GeneratedFallback(GeneratedProseDecision):
    """Generated prose should degrade to safe fallback narration."""

    def __init__(self, *, reason: str, violated_term: str) -> None:
        super().__init__("fallback", reason, violated_term)


@dataclass(frozen=True)
class RetryDecision:
    """Retry/fallback result for a failed narration attempt."""

    action: RetryAction
    reason: str | None = None

    @property
    def should_retry(self) -> bool:
        return self.action == "retry"

    @property
    def should_fallback(self) -> bool:
        return self.action == "fallback"


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

_POST_GATE_SYSTEM_PROMPT = (
    "You are a content safety classifier for a tabletop RPG. "
    "Given a piece of narration text and a list of hard-limit and soft-limit policy terms, "
    "determine whether the text violates any policy. "
    'Respond with JSON: {"verdict": "pass" | "rewrite" | "block_fallback", "reason": string|null, "violated_term": string|null}. '
    'Use "pass" if no policy term is present. '
    'Use "rewrite" if a soft-limit term is present and can be redacted. '
    'Use "block_fallback" if a hard-limit term is present or redaction would not suffice.'
)


def _coerce_policy(policy: ContentPolicy | dict[str, Any] | None) -> ContentPolicy | None:
    if policy is None:
        return None
    return ContentPolicy.model_validate(policy) if isinstance(policy, dict) else policy


def _terms_for(policy_term: str) -> tuple[str, ...]:
    return (policy_term, policy_term.replace("_", " "), *_POLICY_SYNONYMS.get(policy_term, ()))


def _compile_limit_patterns(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        escaped = [re.escape(s) for s in _terms_for(term) if s]
        if escaped:
            combined = "|".join(escaped)
            patterns.append((term, re.compile(rf"\b(?:{combined})\b", re.IGNORECASE)))
        for loose_pattern in _REGEX_SYNONYMS.get(term, ()):  # no word-boundary wrapper
            patterns.append((term, re.compile(loose_pattern, re.IGNORECASE)))
    return patterns


def _redact_text(text: str, term: str) -> str:
    routed = text
    for synonym in _terms_for(term):
        if synonym:
            routed = re.sub(re.escape(synonym), _SAFE_REPLACEMENT, routed, flags=re.IGNORECASE)
    return routed


@dataclass(frozen=True)
class SafetyGuard:
    """One Interface for pre-gate, stream scan, post-gate, events, and fallback policy."""

    llm_client: LLMClient | None = None
    cheap_model: str = "fake-cheap"
    max_rewrites: int = DEFAULT_MAX_REWRITES
    fallback_narration: str = DEFAULT_FALLBACK_NARRATION
    _policy: ContentPolicy | None = field(default=None, repr=False)
    _hard_limit_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    _soft_limit_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    _soft_limit_actions: dict[str, str] = field(default_factory=dict)

    def __init__(
        self,
        policy: ContentPolicy | dict[str, Any] | None = None,
        *,
        llm_client: LLMClient | None = None,
        cheap_model: str = "fake-cheap",
        max_rewrites: int = DEFAULT_MAX_REWRITES,
        fallback_narration: str = DEFAULT_FALLBACK_NARRATION,
    ) -> None:
        cp = _coerce_policy(policy)
        object.__setattr__(self, "llm_client", llm_client)
        object.__setattr__(self, "cheap_model", cheap_model)
        object.__setattr__(self, "max_rewrites", max_rewrites)
        object.__setattr__(self, "fallback_narration", fallback_narration)
        object.__setattr__(self, "_policy", cp)
        object.__setattr__(
            self, "_hard_limit_patterns", _compile_limit_patterns(cp.hard_limits) if cp else []
        )
        object.__setattr__(
            self,
            "_soft_limit_patterns",
            _compile_limit_patterns(list(cp.soft_limits.keys())) if cp else [],
        )
        object.__setattr__(self, "_soft_limit_actions", dict(cp.soft_limits) if cp else {})

    def route_intent(self, scene_intent: str) -> IntentDecision:
        """Apply pre-generation content-policy routing to a scene intent."""

        text = scene_intent.strip()
        lowered = text.lower()

        for term, pattern in self._hard_limit_patterns:
            if not pattern.search(lowered):
                continue
            if lowered in {term.lower(), term.replace("_", " ").lower()}:
                return IntentBlocked(text, reason=f"hard limit blocked: {term}", policy_ref=term)
            safe = _redact_text(text, term)
            if safe != text:
                return IntentRerouted(safe, reason=f"hard limit rerouted: {term}", policy_ref=term)
            return IntentBlocked(text, reason=f"hard limit blocked: {term}", policy_ref=term)

        warnings: list[str] = []
        routed = text
        for term, pattern in self._soft_limit_patterns:
            if not pattern.search(lowered):
                continue
            action = self._soft_limit_actions.get(term, "fade_to_black")
            warnings.append(f"{term}:{action}")
            if action == "ask_first":
                return IntentBlocked(
                    text,
                    reason=f"needs_player_consent: {term}",
                    policy_ref=term,
                )
            routed = _redact_text(routed, term)

        if routed != text:
            return IntentRerouted(
                routed, reason="soft limit adjusted", policy_ref=warnings[0] if warnings else ""
            )

        return IntentAllowed(text, content_warnings=tuple(warnings))

    def check_stream(self, buffer_text: str) -> StreamHit | None:
        """Return first hard-limit hit in buffered stream text, or None."""

        for term, pattern in self._hard_limit_patterns:
            match = pattern.search(buffer_text)
            if match is not None:
                return StreamHit(kind="hard_limit", term=term, matched_text=match.group(0))
        return None

    def scan_generated_prose(self, prose: str) -> GeneratedProseDecision:
        """Scan completed player-facing prose against the configured policy."""

        if self._policy is None or (not self._policy.hard_limits and not self._policy.soft_limits):
            return GeneratedAllowed()

        inline_hard = self._scan_hard_limits(prose)
        if inline_hard is not None:
            return GeneratedFallback(
                reason=f"hard limit found in generated prose: {inline_hard.term}",
                violated_term=inline_hard.term,
            )

        if self.llm_client is None:
            return self._scan_soft_limits(prose)

        return self._llm_classify(prose)

    def retry_or_fallback(self, attempt_index: int, reason: str) -> RetryDecision:
        """Return retry until the rewrite limit is exhausted, then fallback."""

        if attempt_index < self.max_rewrites:
            return RetryDecision("retry", reason)
        return RetryDecision("fallback", reason)

    def make_event(
        self,
        turn_id: str,
        kind: str,
        policy_ref: str | None,
        reason: str,
        *,
        source: str = "safety",
        sequence: int = 0,
    ) -> SafetyEvent:
        """Create a player-visible SafetyEvent value for graph state updates."""

        return SafetyEvent(
            id=f"safety_{turn_id}_{source}_{kind}_{sequence}",
            turn_id=turn_id,
            kind=kind,  # type: ignore[arg-type]
            policy_ref=policy_ref,
            action_taken=reason[:200],
        )

    def _scan_hard_limits(self, prose: str) -> StreamHit | None:
        return self.check_stream(prose)

    def _scan_soft_limits(self, prose: str) -> GeneratedProseDecision:
        for term, pattern in self._soft_limit_patterns:
            if not pattern.search(prose):
                continue
            action = self._soft_limit_actions.get(term, "fade_to_black")
            if action == "ask_first":
                return GeneratedFallback(
                    reason=f"soft limit (ask_first) found in prose: {term}",
                    violated_term=term,
                )
            return GeneratedRewrite(
                reason=f"soft limit ({action}) found in prose: {term}",
                violated_term=term,
                redacted_prose=prose,
            )
        return GeneratedAllowed()

    def _llm_classify(self, prose: str) -> GeneratedProseDecision:
        policy_terms: dict[str, Any] = {
            "hard_limits": self._policy.hard_limits if self._policy else [],
            "soft_limits": dict(self._policy.soft_limits) if self._policy else {},
        }

        request = LLMRequest(
            agent_name="safety_post_gate",
            model=self.cheap_model,
            messages=[
                Message(role="system", content=_POST_GATE_SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=json.dumps(
                        {
                            "narration": prose[:2000],
                            "policy": policy_terms,
                        }
                    ),
                ),
            ],
            response_format="json_schema",
            json_schema={
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["pass", "rewrite", "block_fallback"]},
                    "reason": {"type": ["string", "null"]},
                    "violated_term": {"type": ["string", "null"]},
                },
                "required": ["verdict", "reason", "violated_term"],
            },
            temperature=0.0,
            max_tokens=256,
            timeout_seconds=10,
        )

        try:
            response = self.llm_client.complete(request) if self.llm_client is not None else None
        except Exception:
            return self._scan_soft_limits(prose)

        parsed = (
            response.parsed_json
            if response is not None and isinstance(response.parsed_json, dict)
            else {}
        )
        verdict = parsed.get("verdict", "pass")
        reason = parsed.get("reason")
        violated_term = parsed.get("violated_term")

        if verdict == "block_fallback":
            return GeneratedFallback(
                reason=reason or "LLM classifier flagged hard-limit content",
                violated_term=violated_term or "unknown",
            )
        if verdict == "rewrite":
            return GeneratedRewrite(
                reason=reason or "LLM classifier flagged soft-limit content",
                violated_term=violated_term or "unknown",
            )
        return GeneratedAllowed()
