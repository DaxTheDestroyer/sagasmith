"""In-process no-paid-call smoke harness."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sagasmith.evals.fixtures import make_valid_saga_state
from sagasmith.evals.redaction import RedactionCanary
from sagasmith.evals.schema_round_trip import assert_round_trip
from sagasmith.schemas.export import LLM_BOUNDARY_AND_PERSISTED_MODELS, export_all_schemas
from sagasmith.schemas.validation import PersistedStateError, validate_persisted_state


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
            result.checks.append(SmokeCheck("state.compact_references", True, f"{len(state_json)} bytes"))
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

    return result
