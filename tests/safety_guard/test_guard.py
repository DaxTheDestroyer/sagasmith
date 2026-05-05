"""Tests for the Safety Guard Module Interface."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.safety_guard import (
    GeneratedAllowed,
    GeneratedFallback,
    GeneratedRewrite,
    IntentAllowed,
    IntentBlocked,
    IntentRerouted,
    SafetyGuard,
)
from sagasmith.schemas.player import ContentPolicy
from sagasmith.schemas.provider import LLMRequest, LLMResponse, LLMStreamEvent, TokenUsage


@pytest.fixture
def default_policy() -> ContentPolicy:
    return ContentPolicy(
        hard_limits=["graphic_sexual_content", "harm_to_children"],
        soft_limits={"graphic_violence": "fade_to_black"},
        preferences=["moral_ambiguity_ok"],
    )


def _fake_client(parsed_json: dict[str, Any]) -> DeterministicFakeClient:
    return DeterministicFakeClient(
        scripted_responses={
            "safety_post_gate": LLMResponse(
                text="",
                parsed_json=parsed_json,
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                finish_reason="stop",
                cost_estimate_usd=0.0,
            )
        }
    )


class RecordingClient:
    def __init__(self) -> None:
        self.complete_calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        _ = request
        self.complete_calls += 1
        return LLMResponse(
            text="",
            parsed_json={"verdict": "pass", "reason": None, "violated_term": None},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            finish_reason="stop",
            cost_estimate_usd=0.0,
        )

    def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]:
        _ = request
        return iter(())


def test_no_policy_allows_everything() -> None:
    guard = SafetyGuard(None)

    assert isinstance(guard.route_intent("graphic violence"), IntentAllowed)
    assert guard.check_stream("graphic sexual content") is None
    assert isinstance(guard.scan_generated_prose("graphic sexual content"), GeneratedAllowed)


def test_no_policy_with_llm_does_not_call_classifier() -> None:
    client = RecordingClient()

    decision = SafetyGuard(None, llm_client=client).scan_generated_prose("graphic sexual content")

    assert isinstance(decision, GeneratedAllowed)
    assert client.complete_calls == 0


def test_empty_policy_with_llm_does_not_call_classifier() -> None:
    client = RecordingClient()
    policy = ContentPolicy(hard_limits=[], soft_limits={}, preferences=[])

    decision = SafetyGuard(policy, llm_client=client).scan_generated_prose("graphic sexual content")

    assert isinstance(decision, GeneratedAllowed)
    assert client.complete_calls == 0


def test_exact_hard_limit_blocks(default_policy: ContentPolicy) -> None:
    decision = SafetyGuard(default_policy).route_intent("graphic_sexual_content")

    assert isinstance(decision, IntentBlocked)
    assert decision.policy_ref == "graphic_sexual_content"


def test_hard_limit_sentence_reroutes(default_policy: ContentPolicy) -> None:
    decision = SafetyGuard(default_policy).route_intent(
        "The scene contains graphic sexual content."
    )

    assert isinstance(decision, IntentRerouted)
    assert "safety-aware offscreen complication" in decision.intent


def test_soft_limit_reroutes(default_policy: ContentPolicy) -> None:
    decision = SafetyGuard(default_policy).route_intent("Gore covers the chamber floor.")

    assert isinstance(decision, IntentRerouted)
    assert decision.policy_ref == "graphic_violence:fade_to_black"


def test_ask_first_blocks_and_falls_back() -> None:
    policy = ContentPolicy(
        hard_limits=[],
        soft_limits={"harm_to_children": "ask_first"},
        preferences=[],
    )
    guard = SafetyGuard(policy)

    assert isinstance(guard.route_intent("harm a child is implied"), IntentBlocked)
    assert isinstance(guard.scan_generated_prose("harm a child is implied"), GeneratedFallback)


def test_stream_hit_reports_term_and_text(default_policy: ContentPolicy) -> None:
    hit = SafetyGuard(default_policy).check_stream("A child is seriously harmed.")

    assert hit is not None
    assert hit.kind == "hard_limit"
    assert hit.term == "harm_to_children"
    assert "child" in hit.matched_text.lower()


def test_generated_hard_limit_falls_back_before_llm(default_policy: ContentPolicy) -> None:
    client = _fake_client({"verdict": "pass", "reason": None, "violated_term": None})
    decision = SafetyGuard(default_policy, llm_client=client).scan_generated_prose(
        "The prose contains graphic sexual content."
    )

    assert isinstance(decision, GeneratedFallback)
    assert decision.violated_term == "graphic_sexual_content"


def test_generated_soft_limit_rewrites_without_llm(default_policy: ContentPolicy) -> None:
    decision = SafetyGuard(default_policy).scan_generated_prose("Gore covers the floor.")

    assert isinstance(decision, GeneratedRewrite)
    assert decision.violated_term == "graphic_violence"


@pytest.mark.parametrize(
    ("parsed_json", "expected_type"),
    [
        ({"verdict": "pass", "reason": None, "violated_term": None}, GeneratedAllowed),
        (
            {
                "verdict": "rewrite",
                "reason": "soft limit found",
                "violated_term": "graphic_violence",
            },
            GeneratedRewrite,
        ),
        (
            {
                "verdict": "block_fallback",
                "reason": "hard limit found",
                "violated_term": "graphic_sexual_content",
            },
            GeneratedFallback,
        ),
    ],
)
def test_llm_classifier_verdicts_map_to_decisions(
    default_policy: ContentPolicy,
    parsed_json: dict[str, Any],
    expected_type: type[object],
) -> None:
    decision = SafetyGuard(
        default_policy,
        llm_client=_fake_client(parsed_json),
        cheap_model="fake-cheap",
    ).scan_generated_prose("Ambiguous prose without inline policy terms.")

    assert isinstance(decision, expected_type)


def test_retry_or_fallback_exhausts_after_limit(default_policy: ContentPolicy) -> None:
    guard = SafetyGuard(default_policy, max_rewrites=2)

    assert guard.retry_or_fallback(0, "rewrite").should_retry is True
    assert guard.retry_or_fallback(1, "rewrite").should_retry is True
    assert guard.retry_or_fallback(2, "rewrite").should_fallback is True


def test_make_event_returns_valid_safety_event(default_policy: ContentPolicy) -> None:
    event = SafetyGuard(default_policy).make_event(
        "turn_001",
        "fallback",
        "graphic_violence",
        "x" * 300,
        source="render",
        sequence=2,
    )

    assert event.id == "safety_turn_001_render_fallback_2"
    assert event.turn_id == "turn_001"
    assert event.kind == "fallback"
    assert event.policy_ref == "graphic_violence"
    assert len(event.action_taken) == 200


def test_make_event_sequence_prevents_same_kind_collision(default_policy: ContentPolicy) -> None:
    guard = SafetyGuard(default_policy)

    first = guard.make_event("turn_001", "fallback", None, "one", source="render", sequence=0)
    second = guard.make_event("turn_001", "fallback", None, "two", source="render", sequence=1)

    assert first.id != second.id
