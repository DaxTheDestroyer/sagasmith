"""Tests for Oracle content-policy routing."""

from __future__ import annotations

from sagasmith.agents.oracle.skills.content_policy_routing.logic import (
    Blocked,
    Rerouted,
    route_scene_intent,
)
from sagasmith.evals.fixtures import make_valid_content_policy


def test_hard_limit_reroutes_before_generation() -> None:
    result = route_scene_intent(
        scene_intent="Introduce a graphic sexual threat in the tavern.",
        content_policy=make_valid_content_policy(),
    )

    assert isinstance(result, Rerouted)
    assert "graphic sexual" not in result.intent.lower()
    assert result.policy_ref == "graphic_sexual_content"


def test_hard_limit_blocks_when_intent_only_names_policy() -> None:
    result = route_scene_intent(
        scene_intent="graphic_sexual_content",
        content_policy=make_valid_content_policy(),
    )

    assert isinstance(result, Blocked)
    assert result.policy_ref == "graphic_sexual_content"


def test_soft_limit_adds_warning_or_adjusts() -> None:
    result = route_scene_intent(
        scene_intent="Foreshadow graphic violence near the old ford.",
        content_policy=make_valid_content_policy(),
    )

    assert result.kind in {"allowed", "rerouted"}
    assert result.kind == "rerouted" or result.content_warnings == ("graphic_violence:fade_to_black",)
