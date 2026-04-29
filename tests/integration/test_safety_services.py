"""Integration tests for safety services (pre-gate + post-gate + SafetyEventService).

Service-level integration only — full end-to-end Oracle→Orator safety flow
lives in tests/integration/test_safety_enforcement.py (Task 8).
"""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.evals.fixtures import make_valid_content_policy
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.provider import LLMResponse, TokenUsage
from sagasmith.services.safety import SafetyEventService
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
from tests.fixtures.content_policy_violations import (
    HARD_LIMIT_FIXTURES,
    SOFT_LIMIT_FIXTURES,
    ViolationFixture,
)


@pytest.fixture
def campaign_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("camp-int-safety", "Integration Safety", "int-safety", "2026-01-01T00:00:00Z", "0.0.1"),
    )
    conn.commit()
    return conn


@pytest.fixture
def safety_svc(campaign_conn: sqlite3.Connection) -> SafetyEventService:
    return SafetyEventService(conn=campaign_conn)


# ---------------------------------------------------------------------------
# Pre-gate verdict routing
# ---------------------------------------------------------------------------


class TestPreGateVerdictRouting:
    """Pre-gate returns correct verdict types for representative policy fixtures."""

    def test_allowed_for_safe_content(self) -> None:
        policy = make_valid_content_policy()
        gate = SafetyPreGate(policy)
        verdict = gate.check("The hero explores the old ford.")
        assert isinstance(verdict, Allowed)

    @pytest.mark.parametrize(
        "fixture",
        [f for f in HARD_LIMIT_FIXTURES if f.expected_kind == "hard"],
        ids=lambda f: f.label,
    )
    def test_hard_limit_produces_blocked_or_rerouted(self, fixture: ViolationFixture) -> None:
        policy = make_valid_content_policy()
        gate = SafetyPreGate(policy)
        verdict = gate.check(fixture.text)
        assert isinstance(verdict, (Blocked, Rerouted))

    @pytest.mark.parametrize(
        "fixture",
        [f for f in SOFT_LIMIT_FIXTURES if f.expected_kind == "soft"],
        ids=lambda f: f.label,
    )
    def test_soft_limit_produces_rerouted_or_allowed(self, fixture: ViolationFixture) -> None:
        policy = make_valid_content_policy()
        gate = SafetyPreGate(policy)
        verdict = gate.check(fixture.text)
        assert isinstance(verdict, (Rerouted, Allowed))


# ---------------------------------------------------------------------------
# Post-gate scan + rewrite-decision integration
# ---------------------------------------------------------------------------


class TestPostGateScanIntegration:
    """Post-gate scan with DeterministicFakeClient returning prohibited prose."""

    def test_pass_verdict_for_clean_prose(self) -> None:
        from sagasmith.providers.fake import DeterministicFakeClient

        client = DeterministicFakeClient(
            scripted_responses={
                "safety_post_gate": LLMResponse(
                    text="",
                    parsed_json={"verdict": "pass", "reason": None, "violated_term": None},
                    usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    finish_reason="stop",
                    cost_estimate_usd=0.0,
                ),
            },
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("The hero enters the tavern.", make_valid_content_policy())
        assert isinstance(verdict, Pass)

    def test_rewrite_verdict_for_soft_limit(self) -> None:
        from sagasmith.providers.fake import DeterministicFakeClient

        client = DeterministicFakeClient(
            scripted_responses={
                "safety_post_gate": LLMResponse(
                    text="",
                    parsed_json={
                        "verdict": "rewrite",
                        "reason": "soft limit detected",
                        "violated_term": "graphic_violence",
                    },
                    usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    finish_reason="stop",
                    cost_estimate_usd=0.0,
                ),
            },
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("Gore fills the room.", make_valid_content_policy())
        assert isinstance(verdict, Rewrite)

    def test_block_fallback_verdict_for_hard_limit(self) -> None:
        from sagasmith.providers.fake import DeterministicFakeClient

        client = DeterministicFakeClient(
            scripted_responses={
                "safety_post_gate": LLMResponse(
                    text="",
                    parsed_json={
                        "verdict": "block_fallback",
                        "reason": "hard limit in prose",
                        "violated_term": "graphic_sexual_content",
                    },
                    usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    finish_reason="stop",
                    cost_estimate_usd=0.0,
                ),
            },
        )
        gate = SafetyPostGate(llm_client=client, cheap_model="fake-cheap")
        verdict = gate.scan("Prose with graphic sexual content.", make_valid_content_policy())
        assert isinstance(verdict, BlockFallback)


# ---------------------------------------------------------------------------
# SafetyEventService writes match expected schema
# ---------------------------------------------------------------------------


class TestSafetyEventServiceSchema:
    """SafetyEventService writes match expected schema for each verdict path."""

    def test_pre_gate_block_logged(self, safety_svc: SafetyEventService) -> None:
        record = safety_svc.log_pre_gate_block(
            campaign_id="camp-int-safety",
            policy_ref="graphic_sexual_content",
            reason="hard limit blocked: graphic_sexual_content",
            turn_id="turn-001",
        )
        assert record.kind == "pre_gate_block"
        assert record.policy_ref == "graphic_sexual_content"
        assert "blocked" in record.action_taken
        assert record.campaign_id == "camp-int-safety"

    def test_pre_gate_reroute_logged(self, safety_svc: SafetyEventService) -> None:
        record = safety_svc.log_pre_gate_reroute(
            campaign_id="camp-int-safety",
            policy_ref="graphic_violence",
            reason="soft limit adjusted",
            turn_id="turn-001",
        )
        assert record.kind == "pre_gate_reroute"
        assert record.policy_ref == "graphic_violence"
        assert "rerouted" in record.action_taken

    def test_post_gate_rewrite_logged(self, safety_svc: SafetyEventService) -> None:
        record = safety_svc.log_post_gate_rewrite(
            campaign_id="camp-int-safety",
            policy_ref="graphic_violence",
            reason="soft limit found in prose",
            turn_id="turn-002",
        )
        assert record.kind == "post_gate_rewrite"
        assert "rewrite" in record.action_taken

    def test_fallback_logged(self, safety_svc: SafetyEventService) -> None:
        record = safety_svc.log_fallback(
            campaign_id="camp-int-safety",
            reason="persistent violation after retries",
            turn_id="turn-003",
        )
        assert record.kind == "fallback"
        assert "fallback" in record.action_taken

    def test_all_event_kinds_in_safety_event_record(self) -> None:
        """Verify SafetyEventRecord accepts all Phase 6 event kinds."""
        from sagasmith.schemas.persistence import SafetyEventRecord

        for kind in (
            "pause",
            "line",
            "soft_limit_fade",
            "post_gate_rewrite",
            "fallback",
            "pre_gate_reroute",
            "pre_gate_block",
        ):
            record = SafetyEventRecord(
                event_id=f"test_{kind}",
                campaign_id="camp-test",
                turn_id="turn-test",
                kind=kind,
                policy_ref=None,
                action_taken=f"test:{kind}",
                timestamp="2026-01-01T00:00:00Z",
            )
            assert record.kind == kind
