"""Unit tests for SafetyPostGate service."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.schemas.player import ContentPolicy
from sagasmith.schemas.provider import LLMRequest, LLMResponse, LLMStreamEvent, TokenUsage
from sagasmith.services.safety_post_gate import (
    BlockFallback,
    Pass,
    Rewrite,
    SafetyPostGate,
)


@pytest.fixture
def default_policy() -> ContentPolicy:
    return ContentPolicy(
        hard_limits=["graphic_sexual_content", "harm_to_children"],
        soft_limits={"graphic_violence": "fade_to_black"},
        preferences=["moral_ambiguity_ok"],
    )


def _fake_client(
    parsed_json: dict[str, Any] | None = None,
    *,
    agent: str = "safety_post_gate",
) -> DeterministicFakeClient:
    response = LLMResponse(
        text="",
        parsed_json=parsed_json or {"verdict": "pass", "reason": None, "violated_term": None},
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        finish_reason="stop",
        cost_estimate_usd=0.0,
    )
    return DeterministicFakeClient(scripted_responses={agent: response})


# ---------------------------------------------------------------------------
# Inline hard-limit scan (no LLM)
# ---------------------------------------------------------------------------


class TestInlineScan:
    def test_hard_limit_detected_inline(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan("The scene contains graphic sexual content.", default_policy)
        assert isinstance(verdict, BlockFallback)

    def test_clean_prose_passes_inline(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan("The hero enters the tavern.", default_policy)
        assert isinstance(verdict, Pass)

    def test_no_policy_passes(self) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan("Anything at all.", None)
        assert isinstance(verdict, Pass)

    def test_soft_limit_inline_rewrite(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan("Gore covers the floor.", default_policy)
        assert isinstance(verdict, Rewrite)

    def test_ask_first_inline_blocks(self) -> None:
        policy = ContentPolicy(
            hard_limits=[],
            soft_limits={"harm_to_children": "ask_first"},
            preferences=[],
        )
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan("harm a child is witnessed.", policy)
        assert isinstance(verdict, BlockFallback)


# ---------------------------------------------------------------------------
# LLM classifier scan
# ---------------------------------------------------------------------------


class TestLLMClassifier:
    def test_clean_prose_passes_via_llm(self, default_policy: ContentPolicy) -> None:
        client = _fake_client({"verdict": "pass", "reason": None, "violated_term": None})
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("The hero enters the tavern.", default_policy)
        assert isinstance(verdict, Pass)

    def test_hard_limit_blocked_via_llm(self, default_policy: ContentPolicy) -> None:
        client = _fake_client(
            {
                "verdict": "block_fallback",
                "reason": "hard limit found in prose",
                "violated_term": "graphic_sexual_content",
            }
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("Prose with violations.", default_policy)
        assert isinstance(verdict, BlockFallback)
        assert verdict.violated_term == "graphic_sexual_content"

    def test_soft_limit_rewrite_via_llm(self, default_policy: ContentPolicy) -> None:
        client = _fake_client(
            {
                "verdict": "rewrite",
                "reason": "soft limit violation",
                "violated_term": "graphic_violence",
            }
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("Prose with soft violation.", default_policy)
        assert isinstance(verdict, Rewrite)

    def test_llm_failure_falls_back_to_inline(self, default_policy: ContentPolicy) -> None:
        """If LLM call fails, fall back to inline scan."""

        class FailingClient:
            provider = "fake"

            def complete(self, request: LLMRequest) -> LLMResponse:
                _ = request
                raise RuntimeError("LLM unavailable")

            def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]:
                _ = request
                return iter(())

        gate = SafetyPostGate(llm_client=FailingClient(), cheap_model="fake-cheap")
        # Hard-limit text should still be caught by inline fallback
        verdict = gate.scan("graphic sexual content in the scene", default_policy)
        assert isinstance(verdict, BlockFallback)

    def test_inline_hard_limit_takes_precedence_over_llm(
        self, default_policy: ContentPolicy
    ) -> None:
        """Inline scanner runs first — hard limits are caught before LLM call."""
        client = _fake_client({"verdict": "pass", "reason": None, "violated_term": None})
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("graphic sexual content in the prose", default_policy)
        assert isinstance(verdict, BlockFallback)


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------


class TestVerdictTypes:
    def test_pass_verdict_properties(self) -> None:
        v = Pass()
        assert v.kind == "pass"
        assert v.reason is None
        assert v.violated_term is None

    def test_rewrite_verdict_properties(self) -> None:
        v = Rewrite(reason="soft limit", violated_term="graphic_violence")
        assert v.kind == "rewrite"
        assert v.reason == "soft limit"
        assert v.violated_term == "graphic_violence"

    def test_block_fallback_verdict_properties(self) -> None:
        v = BlockFallback(reason="hard limit", violated_term="harm_to_children")
        assert v.kind == "block_fallback"
        assert v.reason == "hard limit"
        assert v.violated_term == "harm_to_children"
