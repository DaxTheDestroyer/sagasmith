"""Tests for hybrid RulesLawyer intent resolution."""

from __future__ import annotations

import pytest

from sagasmith.evals.fixtures import make_fake_llm_response
from sagasmith.providers import DeterministicFakeClient
from sagasmith.services.cost import CostGovernor
from sagasmith.services.errors import BudgetStopError
from sagasmith.services.intent_resolution import deterministic_intents, resolve_intents


def test_explicit_skill_check_pattern_has_high_confidence_and_dc() -> None:
    candidates = resolve_intents("  ROLL   ATHLETICS   DC 15  ")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.action == "skill_check"
    assert candidate.stat == "athletics"
    assert candidate.dc == 15
    assert candidate.confidence == pytest.approx(0.99)
    assert candidate.source == "deterministic"


def test_common_natural_language_patterns_map_to_supported_stats() -> None:
    cases = [
        ("I climb the crumbling wall", "athletics"),
        ("I tumble past the trap", "acrobatics"),
        ("I track the goblin trail", "survival"),
        ("I intimidate the guard", "intimidation"),
        ("I search the altar", "perception"),
    ]

    for text, stat in cases:
        candidates = deterministic_intents(text, scene_context={"skill_dcs": {stat: 17}})
        assert candidates[0].action == "skill_check"
        assert candidates[0].stat == stat
        assert candidates[0].dc == 17
        assert candidates[0].confidence >= 0.70


def test_llm_fallback_classifies_ambiguous_intent_without_accepting_math() -> None:
    client = DeterministicFakeClient(
        {
            "rules_lawyer.intent-resolution": make_fake_llm_response(
                parsed_json={
                    "candidates": [
                        {
                            "action": "skill_check",
                            "stat": "athletics",
                            "target_id": None,
                            "attack_id": None,
                            "position": None,
                            "confidence": 0.81,
                            "reason": "player wants to overcome an obstacle",
                        }
                    ]
                }
            )
        }
    )

    candidates = resolve_intents(
        "I haul myself up before it collapses",
        scene_context={"skill_dcs": {"athletics": 16}},
        llm_client=client,
        cost_governor=CostGovernor(session_budget_usd=1.0),
    )

    assert candidates[0].source == "llm"
    assert candidates[0].stat == "athletics"
    assert candidates[0].dc == 16


def test_budget_stop_falls_back_to_deterministic_only_hint() -> None:
    class BlockingCostGovernor(CostGovernor):
        def preflight(self, **kwargs):  # type: ignore[no-untyped-def]
            raise BudgetStopError("blocked")

    client = DeterministicFakeClient(
        {"rules_lawyer.intent-resolution": make_fake_llm_response(parsed_json={"candidates": []})}
    )

    candidates = resolve_intents(
        "something ambiguous",
        llm_client=client,
        cost_governor=BlockingCostGovernor(session_budget_usd=0.0),
    )

    assert candidates[0].action == "none"
    assert candidates[0].source == "budget_fallback"
    assert "/check athletics 15" in candidates[0].reason
