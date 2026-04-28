"""SafetyPostGate — post-generation content-policy gate using cheap LLM classifier.

D-06.1 / D-06.6: The post-gate is stateless.  Two-rewrite limit enforcement
lives in the Orator pipeline, not here.  Each scan counts against the same
per-turn budget as rendering (honoured by the caller via ``CostGovernor``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from sagasmith.providers.client import LLMClient
from sagasmith.schemas.player import ContentPolicy
from sagasmith.schemas.provider import LLMRequest, Message

# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

PostVerdictKind = Literal["pass", "rewrite", "block_fallback"]

_POST_GATE_SYSTEM_PROMPT = (
    "You are a content safety classifier for a tabletop RPG. "
    "Given a piece of narration text and a list of hard-limit and soft-limit policy terms, "
    "determine whether the text violates any policy. "
    "Respond with JSON: {\"verdict\": \"pass\" | \"rewrite\" | \"block_fallback\", \"reason\": string|null, \"violated_term\": string|null}. "
    "Use \"pass\" if no policy term is present. "
    "Use \"rewrite\" if a soft-limit term is present and can be redacted. "
    "Use \"block_fallback\" if a hard-limit term is present or redaction would not suffice."
)


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

    def __init__(self, *, reason: str, violated_term: str, redacted_prose: str | None = None) -> None:
        super().__init__("rewrite", reason, violated_term, redacted_prose)


class BlockFallback(PostGateVerdict):
    """Prose blocked — hard-limit content detected; use fallback narration."""

    def __init__(self, *, reason: str, violated_term: str) -> None:
        super().__init__("block_fallback", reason, violated_term)


# ---------------------------------------------------------------------------
# Deterministic inline scanner (cheap, no LLM needed)
# ---------------------------------------------------------------------------

_INLINE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "graphic_sexual_content": ("sexual assault", "explicit sex", "graphic sexual"),
    "harm_to_children": ("harm a child", "children are harmed", "child corpse", "injured child", "child harmed", "harmed child", "children harmed", "harming children"),
    "graphic_violence": ("gore", "dismember", "graphic violence", "viscera"),
}

_INLINE_REGEX: dict[str, tuple[str, ...]] = {
    "harm_to_children": (r"child.{0,30}harm", r"harm.{0,30}child"),
}


def _inline_scan(prose: str, policy: ContentPolicy | None) -> PostGateVerdict:
    """Fast deterministic scan for hard-limit keywords in prose."""
    import re

    if policy is None:
        return Pass()

    lowered = prose.lower()
    for term in policy.hard_limits:
        synonyms = (term, term.replace("_", " "), *_INLINE_SYNONYMS.get(term, ()))
        for syn in synonyms:
            if syn and re.search(rf"\b{re.escape(syn)}\b", lowered, re.IGNORECASE):
                return BlockFallback(
                    reason=f"hard limit found in generated prose: {term}",
                    violated_term=term,
                )
        for loose in _INLINE_REGEX.get(term, ()):
            if re.search(loose, lowered, re.IGNORECASE):
                return BlockFallback(
                    reason=f"hard limit found in generated prose: {term}",
                    violated_term=term,
                )
    return Pass()


# ---------------------------------------------------------------------------
# SafetyPostGate service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyPostGate:
    """Post-generation safety gate.

    Uses a cheap LLM classifier for nuanced content detection.  The inline
    hard-limit scanner runs first (zero cost); the LLM call is only made if
    the inline scan passes.

    Usage::

        gate = SafetyPostGate(llm_client=client, cheap_model="model-name")
        verdict = gate.scan("narration text", policy)
    """

    llm_client: LLMClient | None
    cheap_model: str

    def scan(self, prose: str, policy: ContentPolicy | dict | None = None) -> PostGateVerdict:
        """Scan ``prose`` against content policy.

        1. Inline hard-limit keyword scan (free).
        2. Cheap LLM classifier for soft limits / nuance (budgeted).
        """
        cp: ContentPolicy | None = None
        if policy is not None:
            cp = ContentPolicy.model_validate(policy) if isinstance(policy, dict) else policy

        # Step 1: fast deterministic hard-limit check
        inline = _inline_scan(prose, cp)
        if isinstance(inline, BlockFallback):
            return inline

        # Step 2: cheap LLM classifier (if client available)
        if self.llm_client is None:
            # No LLM available — rely on inline scan only
            return _soft_limit_inline_scan(prose, cp)

        return _llm_classify(self.llm_client, self.cheap_model, prose, cp)


def _soft_limit_inline_scan(prose: str, policy: ContentPolicy | None) -> PostGateVerdict:
    """Fallback deterministic soft-limit scanner when no LLM is available."""
    import re

    if policy is None:
        return Pass()

    lowered = prose.lower()
    for term, action in policy.soft_limits.items():
        synonyms = (term, term.replace("_", " "), *_INLINE_SYNONYMS.get(term, ()))
        matched = False
        for syn in synonyms:
            if syn and re.search(rf"\b{re.escape(syn)}\b", lowered, re.IGNORECASE):
                matched = True
                break
        if not matched:
            for loose in _INLINE_REGEX.get(term, ()):
                if re.search(loose, lowered, re.IGNORECASE):
                    matched = True
                    break
        if matched:
            if action == "ask_first":
                return BlockFallback(
                    reason=f"soft limit (ask_first) found in prose: {term}",
                    violated_term=term,
                )
            return Rewrite(
                reason=f"soft limit ({action}) found in prose: {term}",
                violated_term=term,
                redacted_prose=prose,
            )
    return Pass()


def _llm_classify(
    client: LLMClient,
    cheap_model: str,
    prose: str,
    policy: ContentPolicy | None,
) -> PostGateVerdict:
    """Use cheap LLM classifier to detect content violations."""
    policy_terms: dict[str, Any] = {
        "hard_limits": policy.hard_limits if policy else [],
        "soft_limits": dict(policy.soft_limits) if policy else {},
    }

    request = LLMRequest(
        agent_name="safety_post_gate",
        model=cheap_model,
        messages=[
            Message(role="system", content=_POST_GATE_SYSTEM_PROMPT),
            Message(
                role="user",
                content=json.dumps({
                    "narration": prose[:2000],  # cap input for cheap model
                    "policy": policy_terms,
                }),
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
        response = client.complete(request)
    except Exception:
        # LLM failure → fall back to inline scan
        return _soft_limit_inline_scan(prose, policy)

    parsed = response.parsed_json or {}
    verdict_str = parsed.get("verdict", "pass")
    reason = parsed.get("reason")
    violated_term = parsed.get("violated_term")

    if verdict_str == "block_fallback":
        return BlockFallback(
            reason=reason or "LLM classifier flagged hard-limit content",
            violated_term=violated_term or "unknown",
        )
    if verdict_str == "rewrite":
        return Rewrite(
            reason=reason or "LLM classifier flagged soft-limit content",
            violated_term=violated_term or "unknown",
        )
    return Pass()
