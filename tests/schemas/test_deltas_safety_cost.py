"""Tests for delta, safety, and cost schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sagasmith.schemas import CanonConflict, CostState, SafetyEvent, StateDelta


def make_state_delta(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "delta_1",
        "source": "rules",
        "path": "character_sheet.current_hp",
        "operation": "set",
        "value": 12,
        "reason": "Rules outcome.",
    }
    data.update(overrides)
    return data


def make_cost_state(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "session_budget_usd": 2.5,
        "spent_usd_estimate": 0.75,
        "tokens_prompt": 1000,
        "tokens_completion": 500,
        "warnings_sent": ["70"],
        "hard_stopped": False,
    }
    data.update(overrides)
    return data


def make_safety_event(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "safe_1",
        "turn_id": "turn_1",
        "kind": "pause",
        "policy_ref": None,
        "action_taken": "Paused the scene.",
    }
    data.update(overrides)
    return data


def make_canon_conflict(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "conflict_1",
        "entity_id": "npc_marcus_innkeeper",
        "asserted_fact": "Marcus is a dwarf.",
        "canonical_fact": "Marcus is human.",
        "category": "pc_misbelief",
        "severity": "minor",
        "recommended_resolution": "Let the NPC clarify in dialogue.",
    }
    data.update(overrides)
    return data


def test_state_delta_source_literal() -> None:
    with pytest.raises(ValidationError):
        StateDelta(**make_state_delta(source="llm"))

    for source in ["rules", "oracle", "archivist", "safety", "user"]:
        assert StateDelta(**make_state_delta(source=source)).source == source


def test_state_delta_operation_literal() -> None:
    with pytest.raises(ValidationError):
        StateDelta(**make_state_delta(operation="merge"))

    for operation in ["set", "increment", "append", "remove"]:
        assert StateDelta(**make_state_delta(operation=operation)).operation == operation


def test_cost_state_warnings_literal() -> None:
    with pytest.raises(ValidationError):
        CostState(**make_cost_state(warnings_sent=["70", "90", "100"]))
    with pytest.raises(ValidationError):
        CostState(**make_cost_state(warnings_sent=[70]))

    assert CostState(**make_cost_state(warnings_sent=["70"])).warnings_sent == ["70"]
    assert CostState(**make_cost_state(warnings_sent=["70", "90"])).warnings_sent == ["70", "90"]


def test_safety_event_kind_literal() -> None:
    with pytest.raises(ValidationError):
        SafetyEvent(**make_safety_event(kind="moderation"))

    for kind in ["pause", "line", "soft_limit_fade", "post_gate_rewrite", "fallback"]:
        assert SafetyEvent(**make_safety_event(kind=kind)).kind == kind


def test_canon_conflict_category_and_severity() -> None:
    for category in ["retcon_intent", "pc_misbelief", "narrator_error"]:
        assert CanonConflict(**make_canon_conflict(category=category)).category == category
    for severity in ["minor", "major"]:
        assert CanonConflict(**make_canon_conflict(severity=severity)).severity == severity

    with pytest.raises(ValidationError):
        CanonConflict(**make_canon_conflict(category="continuity"))
    with pytest.raises(ValidationError):
        CanonConflict(**make_canon_conflict(severity="critical"))
