"""Unit tests for SafetyPreGate service."""

from __future__ import annotations

import pytest

from sagasmith.schemas.player import ContentPolicy
from sagasmith.services.safety_pre_gate import (
    Allowed,
    Blocked,
    Rerouted,
    SafetyPreGate,
)


@pytest.fixture
def default_policy() -> ContentPolicy:
    return ContentPolicy(
        hard_limits=["graphic_sexual_content", "harm_to_children"],
        soft_limits={"graphic_violence": "fade_to_black"},
        preferences=["moral_ambiguity_ok"],
    )


# ---------------------------------------------------------------------------
# Allowed verdict
# ---------------------------------------------------------------------------


class TestAllowed:
    def test_safe_content_returns_allowed(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("The hero enters the tavern.")
        assert isinstance(verdict, Allowed)
        assert verdict.intent == "The hero enters the tavern."
        assert verdict.reason is None
        assert verdict.policy_ref is None

    def test_no_policy_returns_allowed(self) -> None:
        gate = SafetyPreGate(None)
        verdict = gate.check("Anything goes including graphic violence.")
        assert isinstance(verdict, Allowed)

    def test_empty_intent_returns_allowed(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("")
        assert isinstance(verdict, Allowed)

    def test_soft_limit_warning_on_allowed(self, default_policy: ContentPolicy) -> None:
        """Soft limit that doesn't match text should still pass."""
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("A calm day at the market.")
        assert isinstance(verdict, Allowed)
        assert verdict.content_warnings == ()


# ---------------------------------------------------------------------------
# Blocked verdict
# ---------------------------------------------------------------------------


class TestBlocked:
    def test_exact_hard_limit_name_blocks(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("graphic_sexual_content")
        assert isinstance(verdict, Blocked)
        assert "graphic_sexual_content" in (verdict.policy_ref or "")

    def test_exact_hard_limit_with_spaces_blocks(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("graphic sexual content")
        assert isinstance(verdict, Blocked)

    def test_ask_first_soft_limit_blocks(self) -> None:
        policy = ContentPolicy(
            hard_limits=[],
            soft_limits={"harm_to_children": "ask_first"},
            preferences=[],
        )
        gate = SafetyPreGate(policy)
        verdict = gate.check("harm a child in the scene")
        assert isinstance(verdict, Blocked)
        assert "needs_player_consent" in (verdict.reason or "")

    def test_hard_limit_synonym_blocks_when_unredactable(self) -> None:
        """When the synonym is the entire text, block instead of reroute."""
        gate = SafetyPreGate(
            ContentPolicy(
                hard_limits=["harm_to_children"],
                soft_limits={},
                preferences=[],
            )
        )
        verdict = gate.check("child corpse")
        assert isinstance(verdict, Blocked | Rerouted)


# ---------------------------------------------------------------------------
# Rerouted verdict
# ---------------------------------------------------------------------------


class TestRerouted:
    def test_hard_limit_in_sentence_reroutes(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("Introduce a graphic sexual threat in the tavern.")
        assert isinstance(verdict, Rerouted)
        assert "graphic sexual" not in verdict.intent.lower()
        assert "safety-aware" in verdict.intent.lower()

    def test_soft_limit_fade_to_black_reroutes(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("Foreshadow graphic violence near the old ford.")
        assert isinstance(verdict, Rerouted)
        assert "graphic violence" not in verdict.intent.lower()

    def test_soft_limit_avoid_detail_reroutes(self) -> None:
        policy = ContentPolicy(
            hard_limits=[],
            soft_limits={"graphic_violence": "avoid_detail"},
            preferences=[],
        )
        gate = SafetyPreGate(policy)
        verdict = gate.check("gore fills the room")
        assert isinstance(verdict, Rerouted)

    def test_rerouted_preserves_non_matching_text(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        original = "The hero investigates the tavern while graphic violence erupts nearby."
        verdict = gate.check(original)
        assert isinstance(verdict, Rerouted)
        assert "hero" in verdict.intent.lower()
        assert "tavern" in verdict.intent.lower()


# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------


class TestPatternCompilation:
    def test_policy_synonyms_detected(self) -> None:
        """Synonyms from _POLICY_SYNONYMS should be detected."""
        gate = SafetyPreGate(
            ContentPolicy(
                hard_limits=["graphic_sexual_content"],
                soft_limits={},
                preferences=[],
            )
        )
        # "sexual assault" is a synonym of graphic_sexual_content
        verdict = gate.check("The NPC threatens sexual assault.")
        assert isinstance(verdict, Blocked | Rerouted)

    def test_case_insensitive_matching(self, default_policy: ContentPolicy) -> None:
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("GRAPHIC VIOLENCE erupts in the arena.")
        assert isinstance(verdict, Rerouted)

    def test_word_boundary_matching(self, default_policy: ContentPolicy) -> None:
        """'graphic' in 'graphics' should not match 'graphic_violence'."""
        gate = SafetyPreGate(default_policy)
        verdict = gate.check("The graphics artist paints a mural.")
        assert isinstance(verdict, Allowed)

    def test_recompile_on_new_policy(self) -> None:
        """Creating a new gate with different policy should use new patterns."""
        policy1 = ContentPolicy(hard_limits=["term_a"], soft_limits={}, preferences=[])
        policy2 = ContentPolicy(hard_limits=["term_b"], soft_limits={}, preferences=[])
        gate1 = SafetyPreGate(policy1)
        gate2 = SafetyPreGate(policy2)
        assert isinstance(gate1.check("term_a"), Blocked | Rerouted)
        assert isinstance(gate1.check("term_b"), Allowed)
        assert isinstance(gate2.check("term_b"), Blocked | Rerouted)
        assert isinstance(gate2.check("term_a"), Allowed)
