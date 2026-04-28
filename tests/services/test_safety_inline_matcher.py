"""Unit tests for SafetyInlineMatcher (D-06.1 inline hard-limit scanner)."""

from __future__ import annotations

import pytest

from sagasmith.schemas.player import ContentPolicy
from sagasmith.services.safety_inline_matcher import InlineMatch, SafetyInlineMatcher


@pytest.fixture
def default_policy() -> ContentPolicy:
    return ContentPolicy(
        hard_limits=["graphic_sexual_content", "harm_to_children"],
        soft_limits={"graphic_violence": "fade_to_black"},
        preferences=["moral_ambiguity_ok"],
    )


class TestSafetyInlineMatcher:
    def test_no_policy_matches_nothing(self) -> None:
        matcher = SafetyInlineMatcher(None)
        assert matcher.match("anything at all") is None

    def test_clean_text_matches_nothing(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        assert matcher.match("The hero enters the tavern.") is None

    def test_hard_limit_detected(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        hit = matcher.match("The scene contains graphic sexual content.")
        assert hit is not None
        assert hit.kind == "hard_limit"
        assert hit.term == "graphic_sexual_content"

    def test_synonym_detected(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        hit = matcher.match("A child is seriously harmed.")
        assert hit is not None
        assert hit.term == "harm_to_children"

    def test_partial_match_respects_boundaries(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        # "harmless" should not match "harm"
        hit = matcher.match("The harmless creature wanders by.")
        assert hit is None

    def test_case_insensitive(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        hit = matcher.match("GRAPHIC SEXUAL CONTENT is described.")
        assert hit is not None

    def test_empty_buffer(self, default_policy: ContentPolicy) -> None:
        matcher = SafetyInlineMatcher(default_policy)
        assert matcher.match("") is None

    def test_dict_policy_input(self) -> None:
        policy = ContentPolicy(
            hard_limits=["graphic_violence"],
            soft_limits={},
            preferences=[],
        )
        matcher = SafetyInlineMatcher(policy)
        hit = matcher.match("Gore covers the walls.")
        assert hit is not None
        assert hit.term == "graphic_violence"


class TestInlineMatch:
    def test_match_properties(self) -> None:
        m = InlineMatch(kind="hard_limit", term="test", matched_text="test text")
        assert m.kind == "hard_limit"
        assert m.term == "test"
        assert m.matched_text == "test text"
