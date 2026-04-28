"""QA-05 regression tests — content policy safety enforcement.

Verifies that prohibited content never reaches ``pending_narration`` through
either the pre-gate (intent blocking) or post-gate (prose scanning) safety
mechanisms.

All tests use ``DeterministicFakeClient`` — no paid LLM calls.
"""

from __future__ import annotations

import sqlite3

import pytest
from tests.fixtures.content_policy_violations import (
    BOUNDARY_FIXTURES,
    HARD_LIMIT_FIXTURES,
    MULTILINGUAL_FIXTURES,
    SOFT_LIMIT_FIXTURES,
    ViolationFixture,
)

from sagasmith.agents.oracle.skills.content_policy_routing.logic import (
    Blocked as SkillBlocked,
)
from sagasmith.agents.oracle.skills.content_policy_routing.logic import (
    Rerouted as SkillRerouted,
)
from sagasmith.agents.oracle.skills.content_policy_routing.logic import (
    safety_pre_gate,
)
from sagasmith.evals.fixtures import make_valid_content_policy
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.player import ContentPolicy
from sagasmith.schemas.provider import LLMResponse, TokenUsage
from sagasmith.services.safety_post_gate import (
    BlockFallback,
    Pass,
    Rewrite,
    SafetyPostGate,
)
from sagasmith.services.safety_pre_gate import (
    Allowed,
    Blocked,
    Rerouted,
    SafetyPreGate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_POLICY = make_valid_content_policy()

# For post-gate tests where graphic_violence is a hard limit (not soft)
_HARD_VIOLENCE_POLICY = ContentPolicy(
    hard_limits=["graphic_sexual_content", "harm_to_children", "graphic_violence"],
    soft_limits={},
    preferences=["moral_ambiguity_ok"],
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("camp-qa05", "QA05 Campaign", "qa05-campaign", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    conn.commit()
    return conn


def _fake_client_with_response(text: str, parsed_json: dict | None = None) -> object:
    """Return a minimal fake-like object that returns the given text."""
    from sagasmith.providers.fake import DeterministicFakeClient

    response = LLMResponse(
        text=text,
        parsed_json=parsed_json,
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        finish_reason="stop",
        cost_estimate_usd=0.0,
    )
    return DeterministicFakeClient(
        scripted_responses={"safety_post_gate": response},
    )


# ---------------------------------------------------------------------------
# Pre-gate: hard limits are blocked before generation
# ---------------------------------------------------------------------------


class TestPreGateHardLimits:
    """QA-05: Hard-limit intents are blocked or rerouted before generation."""

    @pytest.mark.parametrize(
        "fixture",
        [f for f in HARD_LIMIT_FIXTURES if f.expected_kind == "hard"],
        ids=lambda f: f.label,
    )
    def test_hard_limit_blocked_or_rerouted(self, fixture: ViolationFixture) -> None:
        gate = SafetyPreGate(_DEFAULT_POLICY)
        verdict = gate.check(fixture.text)
        assert isinstance(verdict, (Blocked, Rerouted)), (
            f"Expected Blocked or Rerouted for {fixture.label}, got {type(verdict).__name__}"
        )

    def test_hard_limit_only_names_policy_blocks(self) -> None:
        gate = SafetyPreGate(_DEFAULT_POLICY)
        verdict = gate.check("graphic_sexual_content")
        assert isinstance(verdict, Blocked)
        assert "graphic_sexual_content" in (verdict.policy_ref or "")


# ---------------------------------------------------------------------------
# Pre-gate: soft limits are faded/redlined appropriately
# ---------------------------------------------------------------------------


class TestPreGateSoftLimits:
    """QA-05: Soft-limit intents are rerouted with redacted content."""

    @pytest.mark.parametrize(
        "fixture",
        [f for f in SOFT_LIMIT_FIXTURES if f.expected_kind == "soft"],
        ids=lambda f: f.label,
    )
    def test_soft_limit_rerouted_or_allowed_with_warning(self, fixture: ViolationFixture) -> None:
        gate = SafetyPreGate(_DEFAULT_POLICY)
        verdict = gate.check(fixture.text)
        assert isinstance(verdict, (Rerouted, Allowed)), (
            f"Expected Rerouted or Allowed for {fixture.label}, got {type(verdict).__name__}"
        )
        if isinstance(verdict, Rerouted):
            # Redacted text should not contain the original term
            for term in fixture.matching_terms:
                normalized = term.replace("_", " ").lower()
                assert normalized not in verdict.intent.lower() or "safety-aware" in verdict.intent.lower()

    def test_ask_first_blocks(self) -> None:
        """Soft limit with ask_first action should block, not reroute."""
        policy = ContentPolicy(
            hard_limits=["graphic_sexual_content"],
            soft_limits={"harm_to_children": "ask_first"},
            preferences=[],
        )
        gate = SafetyPreGate(policy)
        verdict = gate.check("harm a child in the story")
        assert isinstance(verdict, Blocked)
        assert "needs_player_consent" in (verdict.reason or "")


# ---------------------------------------------------------------------------
# Pre-gate: boundary cases
# ---------------------------------------------------------------------------


class TestPreGateBoundary:
    """QA-05: Boundary cases — partial matches, case sensitivity, safe content."""

    @pytest.mark.parametrize(
        "fixture",
        [f for f in BOUNDARY_FIXTURES if f.expected_kind == "safe"],
        ids=lambda f: f.label,
    )
    def test_safe_content_allowed(self, fixture: ViolationFixture) -> None:
        gate = SafetyPreGate(_DEFAULT_POLICY)
        verdict = gate.check(fixture.text)
        assert isinstance(verdict, Allowed), (
            f"Expected Allowed for {fixture.label}, got {type(verdict).__name__}"
        )

    def test_no_policy_allows_everything(self) -> None:
        gate = SafetyPreGate(None)
        verdict = gate.check("any text with graphic violence or explicit content")
        assert isinstance(verdict, Allowed)


# ---------------------------------------------------------------------------
# Pre-gate: multilingual
# ---------------------------------------------------------------------------


class TestPreGateMultilingual:
    """QA-05: Multilingual content handling."""

    @pytest.mark.parametrize(
        "fixture",
        MULTILINGUAL_FIXTURES,
        ids=lambda f: f.label,
    )
    def test_multilingual_correct_classification(self, fixture: ViolationFixture) -> None:
        gate = SafetyPreGate(_DEFAULT_POLICY)
        verdict = gate.check(fixture.text)
        if fixture.expected_kind == "safe":
            assert isinstance(verdict, Allowed)
        elif fixture.expected_kind == "soft":
            assert isinstance(verdict, (Rerouted, Allowed))


# ---------------------------------------------------------------------------
# Post-gate: prose scanning with fake LLM
# ---------------------------------------------------------------------------


class TestPostGateScan:
    """QA-05: Post-generation prose scanning blocks prohibited content."""

    def test_clean_prose_passes(self) -> None:
        client = _fake_client_with_response(
            "",
            parsed_json={"verdict": "pass", "reason": None, "violated_term": None},
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("The hero enters the tavern.", _DEFAULT_POLICY)
        assert isinstance(verdict, Pass)

    def test_hard_limit_prose_blocked(self) -> None:
        client = _fake_client_with_response(
            "",
            parsed_json={
                "verdict": "block_fallback",
                "reason": "hard limit found",
                "violated_term": "graphic_sexual_content",
            },
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan(
            "The scene contains graphic sexual content.",
            _DEFAULT_POLICY,
        )
        assert isinstance(verdict, BlockFallback)

    def test_soft_limit_prose_triggers_rewrite(self) -> None:
        client = _fake_client_with_response(
            "",
            parsed_json={
                "verdict": "rewrite",
                "reason": "soft limit found",
                "violated_term": "graphic_violence",
            },
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("Gore fills the battlefield.", _DEFAULT_POLICY)
        assert isinstance(verdict, Rewrite)

    def test_inline_hard_limit_blocks_without_llm(self) -> None:
        """Inline scanner catches hard-limit keywords even without LLM."""
        gate = SafetyPostGate(llm_client=None, cheap_model="fake-cheap")
        verdict = gate.scan(
            "The scene describes graphic sexual content in detail.",
            _DEFAULT_POLICY,
        )
        assert isinstance(verdict, BlockFallback)

    def test_no_llm_falls_back_to_inline_soft_scan(self) -> None:
        """Without LLM, soft-limit keywords produce Rewrite via inline scan."""
        gate = SafetyPostGate(llm_client=None, cheap_model="fake-cheap")
        verdict = gate.scan("Gore and viscera cover the floor.", _DEFAULT_POLICY)
        assert isinstance(verdict, Rewrite)

    def test_no_policy_means_pass(self) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="fake-cheap")
        verdict = gate.scan("Any content at all.", None)
        assert isinstance(verdict, Pass)


# ---------------------------------------------------------------------------
# Post-gate: inline hard-limit detection
# ---------------------------------------------------------------------------


class TestPostGateInlineHardLimits:
    """QA-05: Inline hard-limit scanner blocks prohibited prose without LLM."""

    @pytest.mark.parametrize(
        "fixture",
        [
            f for f in HARD_LIMIT_FIXTURES
            if f.expected_kind == "hard" and all(t in _DEFAULT_POLICY.hard_limits for t in f.matching_terms)
        ],
        ids=lambda f: f.label,
    )
    def test_inline_hard_limit_blocks(self, fixture: ViolationFixture) -> None:
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan(fixture.text, _DEFAULT_POLICY)
        assert isinstance(verdict, BlockFallback), (
            f"Expected BlockFallback for {fixture.label}, got {type(verdict).__name__}"
        )

    def test_graphic_violence_blocks_when_configured_as_hard_limit(self) -> None:
        """graphic_violence is a soft limit in _DEFAULT_POLICY but hard in _HARD_VIOLENCE_POLICY."""
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        verdict = gate.scan(
            "The scene contains graphic violence with viscera and gore everywhere.",
            _HARD_VIOLENCE_POLICY,
        )
        assert isinstance(verdict, BlockFallback)


# ---------------------------------------------------------------------------
# Integration: pre-gate + post-gate together
# ---------------------------------------------------------------------------


class TestSafetyIntegration:
    """QA-05: Full safety flow — prohibited content never reaches pending_narration."""

    def test_prohibited_intent_blocked_before_generation(self) -> None:
        """Pre-gate blocks hard-limit intent; prose is never generated."""
        gate = SafetyPreGate(_DEFAULT_POLICY)
        for fixture in HARD_LIMIT_FIXTURES:
            if fixture.expected_kind == "hard":
                verdict = gate.check(fixture.text)
                # Must be blocked or rerouted — never Allowed for hard limits
                assert isinstance(verdict, (Blocked, Rerouted))
                # If blocked, no prose should be generated
                if isinstance(verdict, Blocked):
                    # In real flow, Oracle would post SAFETY_BLOCK and halt
                    assert verdict.kind == "blocked"

    def test_prohibited_prose_blocked_after_generation(self) -> None:
        """Post-gate blocks hard-limit prose even if pre-gate missed it."""
        gate = SafetyPostGate(llm_client=None, cheap_model="unused")
        for fixture in HARD_LIMIT_FIXTURES:
            if fixture.expected_kind == "hard":
                verdict = gate.scan(fixture.text, _HARD_VIOLENCE_POLICY)
                # For fixtures where the term is in hard_limits, must block
                if any(
                    term in _HARD_VIOLENCE_POLICY.hard_limits
                    for term in fixture.matching_terms
                ):
                    assert isinstance(verdict, BlockFallback)

    def test_safe_content_flows_through_both_gates(self) -> None:
        """Safe content passes both pre-gate and post-gate."""
        pre = SafetyPreGate(_DEFAULT_POLICY)
        post = SafetyPostGate(llm_client=None, cheap_model="unused")
        safe_text = "The hero enters the tavern and orders a drink."
        assert isinstance(pre.check(safe_text), Allowed)
        assert isinstance(post.scan(safe_text, _DEFAULT_POLICY), Pass)


# ---------------------------------------------------------------------------
# Skill-level pre-gate compatibility
# ---------------------------------------------------------------------------


class TestSkillPreGateCompatibility:
    """QA-05: Existing Oracle content-policy-routing skill produces consistent results."""

    def test_skill_pre_gate_matches_service_for_hard_limits(self) -> None:
        """The skill-level safety_pre_gate and the service produce equivalent verdicts."""
        for fixture in HARD_LIMIT_FIXTURES:
            if fixture.expected_kind == "hard":
                skill_result = safety_pre_gate(fixture.text, _DEFAULT_POLICY)
                service_gate = SafetyPreGate(_DEFAULT_POLICY)
                service_result = service_gate.check(fixture.text)
                # Both should block or reroute — never allow
                assert isinstance(skill_result, (SkillBlocked, SkillRerouted))
                assert isinstance(service_result, (Blocked, Rerouted))
