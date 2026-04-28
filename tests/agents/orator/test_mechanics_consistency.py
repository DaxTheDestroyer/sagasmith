"""Unit tests for mechanical-consistency audit (D-06.2)."""

from __future__ import annotations

from sagasmith.agents.orator.mechanics_consistency import (
    AuditResult,
    audit_mechanical_consistency,
)
from sagasmith.schemas.mechanics import CheckResult, RollResult


def _make_check_result(
    *,
    proposal_id: str = "check_perception_turn_001",
    degree: str = "success",
    natural: int = 15,
    modifier: int = 5,
    total: int = 20,
    dc: int = 15,
) -> CheckResult:
    return CheckResult(
        proposal_id=proposal_id,
        roll_result=RollResult(
            roll_id="roll_001",
            seed="seed_001",
            die="d20",
            natural=natural,
            modifier=modifier,
            total=total,
            dc=dc,
            timestamp="2026-01-01T00:00:00Z",
        ),
        degree=degree,
        effects=[],
        state_deltas=[],
    )


# ---------------------------------------------------------------------------
# Core audit tests
# ---------------------------------------------------------------------------


class TestAuditMechanicalConsistency:
    def test_empty_prose_passes(self) -> None:
        result = audit_mechanical_consistency("", [])
        assert result.ok is True
        assert result.violations == []

    def test_no_check_results_passes(self) -> None:
        result = audit_mechanical_consistency("You stand in a tavern.", [])
        assert result.ok is True

    def test_success_degree_clean_prose_passes(self) -> None:
        cr = _make_check_result(degree="success")
        prose = "You deftly pick the lock and the door swings open."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is True

    def test_success_degree_with_fail_word_flagged(self) -> None:
        cr = _make_check_result(degree="success")
        prose = "You attempt the lock but your pick fails and breaks."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is False
        assert any("fails" in v for v in result.violations)

    def test_failure_degree_with_success_word_flagged(self) -> None:
        cr = _make_check_result(degree="failure")
        prose = "Your strike hits the target squarely."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is False
        assert any("hits" in v for v in result.violations)

    def test_critical_success_clean_passes(self) -> None:
        cr = _make_check_result(degree="critical_success")
        prose = "Your blade connects with devastating precision."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is True

    def test_critical_failure_clean_passes(self) -> None:
        cr = _make_check_result(degree="critical_failure")
        prose = "Your swing goes wide, and you stumble off balance."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is True

    def test_critical_failure_with_hits_flagged(self) -> None:
        cr = _make_check_result(degree="critical_failure")
        prose = "Your strike hits the enemy and pierces armor."
        result = audit_mechanical_consistency(prose, [cr])
        assert result.ok is False


# ---------------------------------------------------------------------------
# AuditResult type tests
# ---------------------------------------------------------------------------


class TestAuditResult:
    def test_ok_result(self) -> None:
        r = AuditResult(ok=True, violations=[])
        assert r.ok is True
        assert r.violations == []

    def test_failure_result(self) -> None:
        r = AuditResult(ok=False, violations=["violation 1"])
        assert r.ok is False
        assert len(r.violations) == 1
