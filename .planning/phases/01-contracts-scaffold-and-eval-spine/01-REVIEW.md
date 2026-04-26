---
phase: 01-contracts-scaffold-and-eval-spine
reviewed: 2026-04-26T23:30:10Z
depth: standard
files_reviewed: 38
files_reviewed_list:
  - pyproject.toml
  - pyrightconfig.json
  - ruff.toml
  - .pre-commit-config.yaml
  - README.md
  - src/sagasmith/__init__.py
  - src/sagasmith/__main__.py
  - src/sagasmith/cli/main.py
  - src/sagasmith/cli/schema_cmd.py
  - src/sagasmith/cli/smoke_cmd.py
  - src/sagasmith/schemas/__init__.py
  - src/sagasmith/schemas/common.py
  - src/sagasmith/schemas/enums.py
  - src/sagasmith/schemas/player.py
  - src/sagasmith/schemas/narrative.py
  - src/sagasmith/schemas/mechanics.py
  - src/sagasmith/schemas/deltas.py
  - src/sagasmith/schemas/safety_cost.py
  - src/sagasmith/schemas/saga_state.py
  - src/sagasmith/schemas/validation.py
  - src/sagasmith/schemas/export.py
  - src/sagasmith/evals/fixtures.py
  - src/sagasmith/evals/redaction.py
  - src/sagasmith/evals/schema_round_trip.py
  - src/sagasmith/evals/harness.py
  - tests/test_import_and_entry.py
  - tests/schemas/test_player_models.py
  - tests/schemas/test_narrative_models.py
  - tests/schemas/test_mechanics_models.py
  - tests/schemas/test_deltas_safety_cost.py
  - tests/schemas/test_saga_state_refs.py
  - tests/schemas/test_validation_gate.py
  - tests/schemas/test_json_schema_export.py
  - tests/evals/conftest.py
  - tests/evals/test_schema_round_trip.py
  - tests/evals/test_compact_state_invariants.py
  - tests/evals/test_redaction_canary.py
  - tests/evals/test_smoke_cli.py
findings:
  critical: 0
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-26T23:30:10Z  
**Depth:** standard  
**Files Reviewed:** 38  
**Status:** issues_found

## Summary

Reviewed the Phase 1 scaffold, schema contracts, eval/smoke spine, CLI commands, tests, and quality configuration. The code is generally small, deterministic, and offline; `uv run pytest -q` passed with `50 passed` during review. No critical vulnerabilities were found.

The advisory findings below are actionable medium-severity issues around schema invariants, secret canary coverage, fixture validation integrity, and quality-gate strictness.

## Warnings

### WR-01: HP schemas allow impossible current HP values

**File:** `src/sagasmith/schemas/mechanics.py:33-34`; `src/sagasmith/schemas/common.py:114-115`

**Issue:** `CharacterSheet.current_hp` and `CombatantState.current_hp` are only constrained to `ge=0`; neither model verifies `current_hp <= max_hp`. As a result, `validate_persisted_state()` can accept persisted or combat state where a character has more current HP than their maximum HP, which undermines the Phase 1 contract goal of fail-closed state validation before deterministic rules services consume state.

**Fix:** Add model validators to both models and add regression tests for `current_hp > max_hp` rejection.

```python
from pydantic import Field, model_validator

class CharacterSheet(SchemaModel):
    # ... existing fields ...
    max_hp: int = Field(gt=0)
    current_hp: int = Field(ge=0)

    @model_validator(mode="after")
    def _current_hp_not_above_max(self) -> "CharacterSheet":
        if self.current_hp > self.max_hp:
            raise ValueError("current_hp cannot exceed max_hp")
        return self

class CombatantState(SchemaModel):
    # ... existing fields ...
    current_hp: int = Field(ge=0)
    max_hp: int = Field(gt=0)

    @model_validator(mode="after")
    def _current_hp_not_above_max(self) -> "CombatantState":
        if self.current_hp > self.max_hp:
            raise ValueError("current_hp cannot exceed max_hp")
        return self
```

### WR-02: Redaction canary misses common OpenAI project key shape

**File:** `src/sagasmith/evals/redaction.py:10`

**Issue:** The `openai_key` pattern only matches `sk-` followed by alphanumeric characters. Common OpenAI project keys use a `sk-proj-...` prefix and include hyphenated/underscore segments, so they will not be detected by the current canary. This weakens the Phase 1 no-secret regression gate before provider logging and persistence are introduced.

**Fix:** Expand the OpenAI pattern and add a synthetic `sk-proj-...` regression case in `tests/evals/test_redaction_canary.py`.

```python
DEFAULT_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openrouter_key", re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}")),
    ("openai_key", re.compile(r"sk-(?:proj-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})")),
    # ...
)
```

### WR-03: Eval fixture overrides bypass Pydantic validation

**File:** `src/sagasmith/evals/fixtures.py:28-31`

**Issue:** `_with_overrides()` uses `model_copy(update=overrides)`, which does not validate the updated values in Pydantic v2. Any test or future maintainer helper that calls a `make_valid_*` factory with overrides can receive an invalid model instance while assuming the schema contract still holds. This can hide schema regressions in the smoke/eval spine.

**Fix:** Rebuild through `model_validate()` after applying overrides so factory outputs remain contract-valid.

```python
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


def _with_overrides(instance: TModel, overrides: Mapping[str, Any]) -> TModel:
    if not overrides:
        return instance
    data = instance.model_dump(mode="python")
    data.update(overrides)
    return type(instance).model_validate(data)
```

Add a regression test such as `make_valid_saga_state(phase="not_a_phase")` raising `ValidationError`.

### WR-04: Global pyright downgrades can let source type bugs pass the gate

**File:** `pyrightconfig.json:10-11`

**Issue:** `reportArgumentType` and `reportMissingParameterType` are downgraded to warnings globally. Because the Makefile/pre-commit gate runs `uv run pyright`, future argument-type errors in `src/` can exit successfully instead of failing CI/pre-commit. This weakens the advertised strict source quality gate; the summaries note this was done for dynamic test helpers, but the override is not scoped to tests.

**Fix:** Keep source diagnostics as errors and isolate test-only looseness. Options include restoring these diagnostics to errors in the main config and either annotating the dynamic tests, adding targeted `# pyright: ignore[...]` comments for intentional fixture helper calls, or splitting test type checking into a separate relaxed config.

```json
{
  "include": ["src", "tests"],
  "typeCheckingMode": "strict",
  "reportArgumentType": "error",
  "reportMissingParameterType": "error"
}
```

---

_Reviewed: 2026-04-26T23:30:10Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
