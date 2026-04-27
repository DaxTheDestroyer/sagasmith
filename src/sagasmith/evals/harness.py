"""In-process no-paid-call smoke harness."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pydantic

from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_character_sheet,
    make_valid_saga_state,
)
from sagasmith.evals.redaction import RedactionCanary
from sagasmith.evals.schema_round_trip import assert_round_trip
from sagasmith.providers import DeterministicFakeClient, invoke_with_retry
from sagasmith.schemas import LLMRequest, Message
from sagasmith.schemas.export import LLM_BOUNDARY_AND_PERSISTED_MODELS, export_all_schemas
from sagasmith.schemas.provider import TokenUsage
from sagasmith.schemas.validation import PersistedStateError, validate_persisted_state
from sagasmith.services.cost import CostGovernor


@dataclass(frozen=True)
class SmokeCheck:
    """Single smoke-check result line."""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeResult:
    """Collection of smoke checks with stable terminal formatting."""

    checks: list[SmokeCheck] = field(default_factory=list[SmokeCheck])

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def format(self) -> str:
        lines = [
            f"{'OK ' if check.ok else 'FAIL'} {check.name}"
            + (f" — {check.detail}" if check.detail else "")
            for check in self.checks
        ]
        lines.append("")
        lines.append(f"{sum(check.ok for check in self.checks)}/{len(self.checks)} checks passed")
        return "\n".join(lines)


def run_smoke() -> SmokeResult:
    """Run Phase 1 invariant checks without network or provider imports."""

    result = SmokeResult()
    state = make_valid_saga_state()

    try:
        assert_round_trip(state)
        result.checks.append(SmokeCheck("schema.round_trip.saga_state", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.round_trip.saga_state", False, str(exc)))

    bad = state.model_dump(mode="json")
    bad.pop("campaign_id", None)
    try:
        validate_persisted_state(bad)
        result.checks.append(
            SmokeCheck(
                "schema.validation.rejects_missing_field",
                False,
                "Expected PersistedStateError; got none",
            )
        )
    except PersistedStateError:
        result.checks.append(SmokeCheck("schema.validation.rejects_missing_field", True))
    except Exception as exc:
        result.checks.append(
            SmokeCheck(
                "schema.validation.rejects_missing_field",
                False,
                f"Wrong exception type: {type(exc).__name__}",
            )
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export_all_schemas(Path(temp_dir))
            got = {path.name.removesuffix(".schema.json") for path in paths}
            want = {model.__name__ for model in LLM_BOUNDARY_AND_PERSISTED_MODELS}
            if got == want:
                result.checks.append(SmokeCheck("schema.export.full_coverage", True))
            else:
                result.checks.append(
                    SmokeCheck(
                        "schema.export.full_coverage",
                        False,
                        f"missing={sorted(want - got)} extra={sorted(got - want)}",
                    )
                )
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.export.full_coverage", False, str(exc)))

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export_all_schemas(Path(temp_dir))
            blob = "\n".join(path.read_text(encoding="utf-8") for path in paths)
            hits = RedactionCanary().scan(blob)
            if hits:
                result.checks.append(
                    SmokeCheck(
                        "redaction.exported_schemas_clean",
                        False,
                        f"{len(hits)} secret-shaped strings; first={hits[0].label}",
                    )
                )
            else:
                result.checks.append(SmokeCheck("redaction.exported_schemas_clean", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("redaction.exported_schemas_clean", False, str(exc)))

    try:
        state_json = json.dumps(state.model_dump(mode="json"))
        if len(state_json) < 20_000:
            result.checks.append(
                SmokeCheck("state.compact_references", True, f"{len(state_json)} bytes")
            )
        else:
            result.checks.append(
                SmokeCheck(
                    "state.compact_references",
                    False,
                    f"SagaState JSON is {len(state_json)} bytes; STATE-05 requires < 20000",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("state.compact_references", False, str(exc)))

    try:
        cs = make_valid_character_sheet()
        try:
            type(cs).model_validate({**cs.model_dump(), "current_hp": cs.max_hp + 1})
            result.checks.append(
                SmokeCheck(
                    "schema.hp_invariant.rejects_over_max",
                    False,
                    "Expected ValidationError for current_hp > max_hp",
                )
            )
        except pydantic.ValidationError:
            result.checks.append(SmokeCheck("schema.hp_invariant.rejects_over_max", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.hp_invariant.rejects_over_max", False, str(exc)))

    try:
        hits = RedactionCanary().scan("sk-proj-aaaabbbbccccddddeeeeffff")
        labels = [h.label for h in hits]
        if labels == ["openai_project_key"]:
            result.checks.append(SmokeCheck("redaction.openai_project_key.labeled", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "redaction.openai_project_key.labeled",
                    False,
                    f"expected 1 openai_project_key hit, got {len(hits)} hits with labels={labels}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("redaction.openai_project_key.labeled", False, str(exc)))

    try:
        client = DeterministicFakeClient(
            {"default": make_fake_llm_response(text='{"ok":true}', parsed_json={"ok": True})}
        )
        request = LLMRequest(
            agent_name="smoke",
            model="fake-default",
            messages=[Message(role="user", content="ping")],
            response_format="json_schema",
            json_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            temperature=0.0,
            timeout_seconds=10,
        )
        response = invoke_with_retry(
            client,
            request,
            cheap_model="fake-cheap",
            agent_name="smoke",
            turn_id=None,
            logger=lambda r: None,
        )
        if response.parsed_json == {"ok": True}:
            result.checks.append(SmokeCheck("provider.fake.round_trip", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "provider.fake.round_trip",
                    False,
                    f"parsed_json mismatch: {response.parsed_json}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("provider.fake.round_trip", False, str(exc)[:200]))

    try:
        gov = CostGovernor(1.0)
        update1 = gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.75
            ),
        )
        update2 = gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.10
            ),
        )
        if update1.warnings_fired_this_call == ["70"] and update2.warnings_fired_this_call == []:
            result.checks.append(SmokeCheck("cost.warning.fires_once_per_threshold", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "cost.warning.fires_once_per_threshold",
                    False,
                    f"update1={update1.warnings_fired_this_call} update2={update2.warnings_fired_this_call}",
                )
            )
    except Exception as exc:
        result.checks.append(
            SmokeCheck("cost.warning.fires_once_per_threshold", False, str(exc)[:200])
        )

    try:
        gov = CostGovernor(1.0)
        gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.95
            ),
        )
        result_preflight = gov.preflight(
            provider="fake",
            model="fake-default",
            prompt_tokens=10000,
            max_tokens_fallback=100000,
        )
        if result_preflight.blocked is True and gov.state.spent_usd_estimate == 0.95:
            result.checks.append(SmokeCheck("cost.hard_stop.before_call", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "cost.hard_stop.before_call",
                    False,
                    f"blocked={result_preflight.blocked} spent={gov.state.spent_usd_estimate}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("cost.hard_stop.before_call", False, str(exc)[:200]))

    try:
        from sagasmith.persistence.db import campaign_db
        from sagasmith.persistence.migrations import apply_migrations
        from sagasmith.persistence.repositories import (
            CheckpointRefRepository,
            CostLogRepository,
            ProviderLogRepository,
            RollLogRepository,
            StateDeltaRepository,
            TranscriptRepository,
            TurnRecordRepository,
        )
        from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
        from sagasmith.schemas.mechanics import RollResult
        from sagasmith.schemas.persistence import (
            CheckpointRef,
            CostLogRecord,
            StateDeltaRecord,
            TranscriptEntry,
            TurnRecord,
        )
        from sagasmith.schemas.provider import ProviderLogRecord

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.db"
            with campaign_db(path) as conn:
                apply_migrations(conn)
                bundle = TurnCloseBundle(
                    turn_record=TurnRecord(
                        turn_id="smoke_t1",
                        campaign_id="c1",
                        session_id="s1",
                        status="complete",
                        started_at="2026-04-26T12:00:00Z",
                        completed_at="2026-04-26T12:00:00Z",
                        schema_version=1,
                    ),
                    transcript_entries=[
                        TranscriptEntry(
                            turn_id="smoke_t1",
                            kind="player_input",
                            content="hello",
                            sequence=0,
                            created_at="2026-04-26T12:00:00Z",
                        )
                    ],
                    roll_results=[
                        (
                            RollResult(
                                roll_id="smoke_r1",
                                seed="s",
                                die="d20",
                                natural=10,
                                modifier=0,
                                total=10,
                                dc=None,
                                timestamp="2026-04-26T12:00:00Z",
                            ),
                            "smoke_t1",
                        )
                    ],
                    provider_logs=[
                        ProviderLogRecord(
                            request_id="smoke_req1",
                            provider="fake",
                            model="m",
                            agent_name="a",
                            turn_id="smoke_t1",
                            failure_kind="none",
                            retry_count=0,
                            latency_ms=0,
                            response_hash="abc",
                            timestamp="2026-04-26T12:00:00Z",
                        )
                    ],
                    state_deltas=[
                        StateDeltaRecord(
                            turn_id="smoke_t1",
                            delta_id="smoke_d1",
                            source="rules",
                            path="hp",
                            operation="set",
                            value_json="10",
                            reason="init",
                            applied_at="2026-04-26T12:00:00Z",
                        )
                    ],
                    cost_logs=[
                        CostLogRecord(
                            turn_id="smoke_t1",
                            provider="fake",
                            model="m",
                            agent_name="a",
                            cost_usd=0.0,
                            cost_is_approximate=True,
                            tokens_prompt=0,
                            tokens_completion=0,
                            warnings_fired=[],
                            spent_usd_after=0.0,
                            timestamp="2026-04-26T12:00:00Z",
                        )
                    ],
                    checkpoint_refs=[
                        CheckpointRef(
                            checkpoint_id="smoke_cp1",
                            turn_id="smoke_t1",
                            kind="final",
                            created_at="2026-04-26T12:00:00Z",
                        )
                    ],
                )
                close_turn(conn, bundle)

                tr = TurnRecordRepository(conn)
                turn = tr.get("smoke_t1")
                ok = (
                    turn is not None
                    and turn.status == "complete"
                    and len(TranscriptRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(RollLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(ProviderLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(StateDeltaRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(CostLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(CheckpointRefRepository(conn).list_for_turn("smoke_t1")) == 1
                )
                if ok:
                    result.checks.append(
                        SmokeCheck("persistence.turn_close.transaction_ordering", True)
                    )
                else:
                    result.checks.append(
                        SmokeCheck(
                            "persistence.turn_close.transaction_ordering",
                            False,
                            "row counts or turn status mismatch",
                        )
                    )
    except Exception as exc:
        result.checks.append(
            SmokeCheck("persistence.turn_close.transaction_ordering", False, str(exc)[:200])
        )

    return result
