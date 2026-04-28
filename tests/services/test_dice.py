"""Tests for DiceService seeded determinism."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sagasmith.services.dice import DiceService


@pytest.mark.smoke
def test_replay_same_seed_same_inputs_produces_same_result() -> None:
    dice1 = DiceService(campaign_seed="c", session_seed="s")
    dice2 = DiceService(campaign_seed="c", session_seed="s")
    r1 = dice1.roll_d20(purpose="perception", actor_id="pc1", modifier=3, roll_index=0)
    r2 = dice2.roll_d20(purpose="perception", actor_id="pc1", modifier=3, roll_index=0)
    assert r1.natural == r2.natural


def test_roll_d20_returns_rollresult_with_all_fields() -> None:
    dice = DiceService(campaign_seed="c", session_seed="s")
    result = dice.roll_d20(purpose="perception", actor_id="pc1", modifier=3, roll_index=0, dc=15)
    assert result.die == "d20"
    assert 1 <= result.natural <= 20
    assert result.total == result.natural + 3
    assert result.dc == 15
    assert result.roll_id == "roll_perception_pc1_000000"
    assert result.seed == "c:s"
    assert result.timestamp


def test_different_session_seed_changes_natural() -> None:
    dice1 = DiceService(campaign_seed="c", session_seed="s1")
    dice2 = DiceService(campaign_seed="c", session_seed="s2")
    differences = 0
    for i in range(10):
        r1 = dice1.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=i)
        r2 = dice2.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=i)
        if r1.natural != r2.natural:
            differences += 1
    assert differences >= 1


def test_roll_index_changes_natural() -> None:
    dice = DiceService(campaign_seed="c", session_seed="s")
    values = {
        dice.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=i).natural
        for i in range(20)
    }
    assert len(values) >= 10


def test_timestamp_uses_injected_clock() -> None:
    fixed = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    dice = DiceService(campaign_seed="c", session_seed="s", clock=lambda: fixed)
    result = dice.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=0)
    assert result.timestamp == fixed.isoformat()


def test_roll_rejects_invalid_die_string() -> None:
    dice = DiceService(campaign_seed="c", session_seed="s")
    with pytest.raises(ValueError):
        dice.roll(die="d1", purpose="p", actor_id="a", modifier=0, roll_index=0)
    with pytest.raises(ValueError):
        dice.roll(die="d1001", purpose="p", actor_id="a", modifier=0, roll_index=0)
    with pytest.raises(ValueError):
        dice.roll(die="notadie", purpose="p", actor_id="a", modifier=0, roll_index=0)


def test_roll_d4_natural_in_range() -> None:
    dice = DiceService(campaign_seed="c", session_seed="s")
    result = dice.roll(die="d4", purpose="p", actor_id="a", modifier=0, roll_index=0)
    assert 1 <= result.natural <= 4


def test_roll_d8_replays_with_same_seed_and_inputs() -> None:
    dice1 = DiceService(campaign_seed="c", session_seed="s")
    dice2 = DiceService(campaign_seed="c", session_seed="s")

    r1 = dice1.roll(die="d8", purpose="damage", actor_id="pc1", modifier=4, roll_index=3)
    r2 = dice2.roll(die="d8", purpose="damage", actor_id="pc1", modifier=4, roll_index=3)

    assert r1 == r2
    assert 1 <= r1.natural <= 8
    assert r1.total == r1.natural + 4


def test_roll_d6_replays_with_same_seed_and_inputs() -> None:
    dice1 = DiceService(campaign_seed="c", session_seed="s")
    dice2 = DiceService(campaign_seed="c", session_seed="s")

    r1 = dice1.roll(die="d6", purpose="damage", actor_id="enemy1", modifier=0, roll_index=5)
    r2 = dice2.roll(die="d6", purpose="damage", actor_id="enemy1", modifier=0, roll_index=5)

    assert r1 == r2
    assert 1 <= r1.natural <= 6
    assert r1.total == r1.natural


def test_dc_flows_through_to_result() -> None:
    dice = DiceService(campaign_seed="c", session_seed="s")
    with_dc = dice.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=0, dc=15)
    without_dc = dice.roll_d20(purpose="p", actor_id="a", modifier=0, roll_index=1)
    assert with_dc.dc == 15
    assert without_dc.dc is None
