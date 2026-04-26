"""Schema round-trip and persisted-state rejection smoke tests."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from sagasmith.evals.fixtures import (
    make_valid_character_sheet,
    make_valid_content_policy,
    make_valid_cost_state,
    make_valid_house_rules,
    make_valid_memory_packet,
    make_valid_player_profile,
    make_valid_saga_state,
    make_valid_session_state,
)
from sagasmith.evals.schema_round_trip import (
    assert_fixture_rejects,
    assert_fixture_round_trips,
    assert_round_trip,
)
from sagasmith.schemas.export import LLM_BOUNDARY_AND_PERSISTED_MODELS
from sagasmith.schemas.validation import validate_persisted_state

pytestmark = pytest.mark.smoke


FACTORIES: dict[str, Callable[[], object]] = {
    "CharacterSheet": make_valid_character_sheet,
    "ContentPolicy": make_valid_content_policy,
    "CostState": make_valid_cost_state,
    "HouseRules": make_valid_house_rules,
    "MemoryPacket": make_valid_memory_packet,
    "PlayerProfile": make_valid_player_profile,
    "SagaState": make_valid_saga_state,
    "SessionState": make_valid_session_state,
}


def test_valid_fixture_round_trips(valid_state_path):
    assert_fixture_round_trips(valid_state_path)


def test_valid_fixture_matches_canonical_factory(valid_state_path):
    fixture_state = validate_persisted_state(
        json.loads(valid_state_path.read_text(encoding="utf-8"))
    )
    assert fixture_state == make_valid_saga_state()


def test_missing_field_rejected(missing_field_path):
    assert_fixture_rejects(missing_field_path, "campaign_id")


def test_bad_enum_rejected(bad_enum_path):
    assert_fixture_rejects(bad_enum_path, "phase")


def test_every_boundary_model_round_trips():
    round_tripped = 0
    skipped: list[str] = []
    for model_cls in LLM_BOUNDARY_AND_PERSISTED_MODELS:
        factory = FACTORIES.get(model_cls.__name__)
        if factory is None:
            skipped.append(model_cls.__name__)
            continue
        instance = factory()
        assert_round_trip(instance)
        round_tripped += 1

    assert round_tripped >= 8, (
        f"expected at least 8 round-trips, got {round_tripped}; skipped={skipped}"
    )
