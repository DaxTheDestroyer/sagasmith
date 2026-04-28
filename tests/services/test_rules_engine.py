"""Tests for deterministic rules engine check resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from sagasmith.rules import make_first_slice_character
from sagasmith.services.dice import DiceService
from sagasmith.services.pf2e import compute_degree
from sagasmith.services.rules_engine import RulesEngine


_FIXED_TIME = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)


class ExplodingDice:
    def roll_d20(self, **_: object) -> object:
        raise AssertionError("unsupported stats must fail before rolling")


def test_resolve_check_uses_skill_modifier_and_auditable_roll_id() -> None:
    sheet = make_first_slice_character()
    dice = DiceService(campaign_seed="campaign", session_seed="session", clock=lambda: _FIXED_TIME)
    engine = RulesEngine(dice=dice)

    result = engine.resolve_check(
        sheet,
        stat="athletics",
        dc=15,
        reason="force stuck gate",
        roll_index=0,
    )

    assert result.proposal_id == "check_athletics_000000"
    assert result.roll_result.roll_id == "roll_athletics_pc_valeros_first_slice_000000"
    assert result.roll_result.modifier == sheet.skills["athletics"]
    assert result.roll_result.dc == 15
    assert result.roll_result.timestamp == _FIXED_TIME.isoformat()
    assert result.degree == compute_degree(
        natural=result.roll_result.natural,
        total=result.roll_result.total,
        dc=15,
    )
    assert result.effects == []
    assert result.state_deltas == []


def test_resolve_check_uses_perception_modifier() -> None:
    sheet = make_first_slice_character()
    dice = DiceService(campaign_seed="campaign", session_seed="session", clock=lambda: _FIXED_TIME)
    engine = RulesEngine(dice=dice)

    result = engine.resolve_check(
        sheet,
        stat="perception",
        dc=14,
        reason="notice ambush",
        roll_index=1,
        kind="initiative",
    )

    assert result.proposal_id == "check_perception_000001"
    assert result.roll_result.roll_id == "roll_perception_pc_valeros_first_slice_000001"
    assert result.roll_result.modifier == sheet.perception_modifier
    assert result.roll_result.dc == 14


def test_build_check_proposal_is_deterministic_and_secret_false() -> None:
    sheet = make_first_slice_character()
    engine = RulesEngine(dice=DiceService(campaign_seed="campaign", session_seed="session"))

    proposal = engine.build_check_proposal(
        sheet,
        stat="athletics",
        dc=15,
        reason="force stuck gate",
        target_id="gate_01",
    )

    assert proposal.id == "check_athletics_000000"
    assert proposal.reason == "force stuck gate"
    assert proposal.kind == "skill"
    assert proposal.actor_id == sheet.id
    assert proposal.target_id == "gate_01"
    assert proposal.stat == "athletics"
    assert proposal.modifier == sheet.skills["athletics"]
    assert proposal.dc == 15
    assert proposal.secret is False


def test_unsupported_stats_raise_value_error_before_rolling() -> None:
    sheet = make_first_slice_character()
    engine = RulesEngine(dice=cast(DiceService, ExplodingDice()))

    with pytest.raises(ValueError, match="unsupported check stat"):
        engine.resolve_check(
            sheet,
            stat="arcana",
            dc=15,
            reason="identify rune",
            roll_index=2,
        )
