"""Tests for graph state, routing, and import guards."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

from sagasmith.evals.fixtures import make_valid_saga_state, make_valid_scene_brief
from sagasmith.graph.routing import PHASE_TO_ENTRY, route_by_phase, should_route_to_oracle
from sagasmith.graph.state import SagaGraphState, from_saga_state, to_saga_state
from sagasmith.schemas.enums import Phase
from sagasmith.schemas.export import LLM_BOUNDARY_AND_PERSISTED_MODELS
from sagasmith.schemas.saga_state import SagaState

if TYPE_CHECKING:
    from pathlib import Path


class TestSagaGraphState:
    def test_typeddict_keys_match_pydantic_fields(self) -> None:
        """Test 1: SagaGraphState keys exactly match SagaState field names."""
        assert set(SagaGraphState.__annotations__.keys()) == set(SagaState.model_fields.keys())

    def test_pending_narration_field_exists_with_default(self) -> None:
        """Test 2: SagaState has pending_narration with default []."""
        assert "pending_narration" in SagaState.model_fields
        state = make_valid_saga_state()
        assert state.pending_narration == []
        # Backward-compatible: construct without explicit pending_narration
        data = make_valid_saga_state().model_dump()
        data.pop("pending_narration", None)
        state2 = SagaState.model_validate(data)
        assert state2.pending_narration == []

    def test_round_trip_preserves_pending_narration(self) -> None:
        """Test 9: Round-trip through from_saga_state / to_saga_state is byte-equivalent."""
        original = make_valid_saga_state(pending_narration=["line one", "line two"])
        graph_state = from_saga_state(original)
        recovered = to_saga_state(graph_state)
        assert original.model_dump() == recovered.model_dump()


class TestRouteByPhase:
    def test_onboarding_and_character_creation_route_to_onboarding(self) -> None:
        """Test 3: onboarding/character_creation → onboarding node."""
        for phase in ("onboarding", "character_creation"):
            state: SagaGraphState = {"phase": phase}  # type: ignore[typeddict-item]
            assert route_by_phase(state) == "onboarding"

    def test_play_routes_to_oracle(self) -> None:
        """Test 4: play → oracle."""
        state: SagaGraphState = {"phase": "play"}  # type: ignore[typeddict-item]
        assert route_by_phase(state) == "oracle"

    def test_paused_session_end_combat_route_to_end(self) -> None:
        """Test 5: paused/session_end → END sentinel (identity)."""
        from langgraph.graph import END

        for phase in ("paused", "session_end"):
            state: SagaGraphState = {"phase": phase}  # type: ignore[typeddict-item]
            result = route_by_phase(state)
            assert result is END, f"phase={phase!r} expected END, got {result!r}"

    def test_combat_routes_to_rules_lawyer(self) -> None:
        """Phase 5: combat routes into deterministic RulesLawyer mechanics."""
        state: SagaGraphState = {"phase": "combat"}  # type: ignore[typeddict-item]
        assert route_by_phase(state) == "rules_lawyer"

    def test_phase_to_entry_covers_all_enum_values(self) -> None:
        """Test 6: PHASE_TO_ENTRY covers every Phase literal."""
        enum_values = {p.value for p in Phase}
        routed_values = set(PHASE_TO_ENTRY.keys())
        assert enum_values == routed_values

    def test_mechanics_state_fields_remain_in_graph_contract(self) -> None:
        """Phase 5: graph state carries checks and combat state between turns."""
        assert "check_results" in SagaGraphState.__annotations__
        assert "combat_state" in SagaGraphState.__annotations__

    def test_scene_lifecycle_fields_remain_in_graph_contract(self) -> None:
        assert "resolved_beat_ids" in SagaGraphState.__annotations__
        assert "oracle_bypass_detected" in SagaGraphState.__annotations__

    def test_play_skips_oracle_when_scene_beats_unresolved(self) -> None:
        brief = make_valid_scene_brief()
        state = make_valid_saga_state(
            phase="play",
            scene_brief=brief,
            resolved_beat_ids=[brief.beat_ids[0]],
        ).model_dump()

        assert should_route_to_oracle(state) is False
        assert route_by_phase(state) == "rules_lawyer"

    def test_play_routes_to_oracle_when_all_beats_resolved(self) -> None:
        brief = make_valid_scene_brief()
        state = make_valid_saga_state(
            phase="play",
            scene_brief=brief,
            resolved_beat_ids=brief.beat_ids,
        ).model_dump()

        assert should_route_to_oracle(state) is True


class TestLightweightImports:
    def test_graph_package_does_not_import_textual(self) -> None:
        """Test 7: Importing sagasmith.graph does NOT pull textual.

        sqlite3 is now legitimately imported via activation_log, checkpoints,
        and runtime modules (Plan 04-02). Only textual remains deferred.
        """
        code = (
            "import sys; "
            "import sagasmith.graph; "
            "assert 'textual' not in sys.modules, 'textual was imported'; "
            "print('ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


class TestJsonSchemaExport:
    def test_saga_state_schema_includes_pending_narration(self, tmp_path: Path) -> None:
        """Test 8: JSON Schema export emits pending_narration in SagaState."""
        from sagasmith.schemas.export import export_all_schemas

        paths = export_all_schemas(tmp_path)
        saga_schema_path = next(p for p in paths if p.name == "SagaState.schema.json")
        schema = json.loads(saga_schema_path.read_text(encoding="utf-8"))
        assert "pending_narration" in schema.get("properties", {})

    def test_boundary_model_count(self) -> None:
        """Boundary model count includes Phase 6 worldgen LLM-boundary schemas."""
        assert len(LLM_BOUNDARY_AND_PERSISTED_MODELS) == 31
