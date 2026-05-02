"""Tests for the Turn Start Module Interface.

All tests call build_turn_start directly — no Textual or graph plumbing.
"""

from __future__ import annotations

from sagasmith.graph.state import to_saga_state
from sagasmith.turn_start import TurnStartContext, build_turn_start


def _ctx(**overrides: object) -> TurnStartContext:
    defaults: dict[str, object] = {
        "campaign_id": "campaign-abc",
        "session_id": "session_001",
        "session_number": 1,
        "current_turn_id": None,
        "session_budget_usd": 5.0,
        "snapshot_values": None,
    }
    defaults.update(overrides)
    return TurnStartContext(**defaults)  # type: ignore[arg-type]


def test_fresh_first_turn_seeds_first_slice_character() -> None:
    result = build_turn_start(_ctx(), "look around")
    sheet = result.state["character_sheet"]
    assert isinstance(sheet, dict)
    assert sheet["name"] == "Valeros"
    assert result.state["phase"] == "play"


def test_continued_combat_phase_carries_combat_state() -> None:
    combat = {"combatants": [], "round": 1}
    result = build_turn_start(
        _ctx(snapshot_values={"turn_id": "turn_000002", "combat_state": combat}),
        "attack",
    )
    assert result.state["phase"] == "combat"
    assert result.state["combat_state"] is combat


def test_pending_narration_carries_over() -> None:
    lines = ["The wolf snarls.", "You step back.", "It advances."]
    result = build_turn_start(
        _ctx(snapshot_values={"turn_id": "turn_000001", "pending_narration": lines}),
        "run",
    )
    assert result.state["pending_narration"] == lines


def test_check_results_and_state_deltas_carry_over() -> None:
    checks = [{"kind": "skill", "outcome": "success"}]
    deltas = [{"field": "hp", "delta": -5}]
    result = build_turn_start(
        _ctx(
            snapshot_values={
                "turn_id": "turn_000003",
                "check_results": checks,
                "state_deltas": deltas,
            }
        ),
        "rest",
    )
    assert result.state["check_results"] == checks
    assert result.state["state_deltas"] == deltas


def test_session_number_appears_in_session_state() -> None:
    result = build_turn_start(_ctx(session_number=3), "look")
    session_state = result.state["session_state"]
    assert isinstance(session_state, dict)
    assert session_state["session_number"] == 3


def test_existing_character_sheet_not_overwritten_by_first_slice() -> None:
    custom_sheet = {"name": "Seoni", "class": "Sorcerer", "level": 3}
    result = build_turn_start(
        _ctx(snapshot_values={"turn_id": "turn_000001", "character_sheet": custom_sheet}),
        "cast spell",
    )
    assert result.state["character_sheet"] is custom_sheet


def test_cost_state_uses_provided_budget() -> None:
    result = build_turn_start(_ctx(session_budget_usd=12.5), "look")
    cost = result.state["cost_state"]
    assert isinstance(cost, dict)
    assert cost["session_budget_usd"] == 12.5
    assert cost["spent_usd_estimate"] == 0.0
    assert cost["tokens_prompt"] == 0
    assert cost["hard_stopped"] is False


def test_turn_id_progresses_monotonically() -> None:
    result = build_turn_start(
        _ctx(
            current_turn_id="turn_000007",
            snapshot_values={"turn_id": "turn_000007"},
        ),
        "look",
    )
    assert result.next_turn_id == "turn_000008"
    assert result.state["turn_id"] == "turn_000008"


def test_turn_id_first_turn_defaults_to_turn_000001() -> None:
    result = build_turn_start(_ctx(current_turn_id=None, snapshot_values=None), "look")
    assert result.state["turn_id"] == "turn_000001"
    assert result.next_turn_id == "turn_000001"


def test_resume_does_not_double_bump_turn_id() -> None:
    result = build_turn_start(
        _ctx(
            current_turn_id="turn_000005",
            snapshot_values={"turn_id": "turn_000005"},
        ),
        "look",
    )
    assert result.next_turn_id == "turn_000006"


def test_returned_state_validates_against_saga_state() -> None:
    result = build_turn_start(
        _ctx(
            snapshot_values={
                "turn_id": "turn_000001",
                "vault_master_path": "/campaigns/test/master",
                "vault_player_path": "/campaigns/test/player",
            }
        ),
        "look",
    )
    # Raises if any SagaState required field is missing or fails validation.
    to_saga_state(result.state)
