---
phase: 01-contracts-scaffold-and-eval-spine
plan: 02
subsystem: state-schemas
tags: [python, pydantic-v2, typer, json-schema, pytest, ruff, pyright]

requires:
  - phase: 01-contracts-scaffold-and-eval-spine
    provides: uv-managed Python scaffold, sagasmith CLI, strict quality gates, and empty schemas package
provides:
  - Strict Pydantic v2 contracts for SagaState, player configuration, narrative memory, mechanics, state deltas, safety events, and cost state
  - Persisted-state validation gate translating untrusted checkpoint data failures into PersistedStateError
  - Deterministic JSON Schema exporter for 16 LLM-boundary and persisted models
  - sagasmith schema export Typer subcommand with generated schema artifacts ignored except schemas/.gitkeep
affects: [phase-01-plan-03, deterministic-services, graph-runtime, provider-structured-output, persistence-checkpoints, eval-spine]

tech-stack:
  added: []
  patterns:
    - Fail-closed Pydantic BaseModel via ConfigDict(extra="forbid", strict=True, frozen=False)
    - RED/GREEN TDD commits for schema contracts and validation/export surfaces
    - Deterministic schema generation using sorted model order, sorted JSON keys, and trailing newlines

key-files:
  created:
    - src/sagasmith/schemas/enums.py
    - src/sagasmith/schemas/common.py
    - src/sagasmith/schemas/player.py
    - src/sagasmith/schemas/narrative.py
    - src/sagasmith/schemas/mechanics.py
    - src/sagasmith/schemas/deltas.py
    - src/sagasmith/schemas/safety_cost.py
    - src/sagasmith/schemas/saga_state.py
    - src/sagasmith/schemas/validation.py
    - src/sagasmith/schemas/export.py
    - src/sagasmith/cli/schema_cmd.py
    - schemas/.gitkeep
    - tests/schemas/__init__.py
    - tests/schemas/test_player_models.py
    - tests/schemas/test_narrative_models.py
    - tests/schemas/test_mechanics_models.py
    - tests/schemas/test_deltas_safety_cost.py
    - tests/schemas/test_saga_state_refs.py
    - tests/schemas/test_validation_gate.py
    - tests/schemas/test_json_schema_export.py
  modified:
    - .gitignore
    - src/sagasmith/schemas/__init__.py
    - src/sagasmith/cli/main.py

key-decisions:
  - "Used Literal-typed fields for model-facing values so persisted JSON strings validate directly under strict Pydantic mode while still defining StrEnum classes as exported project vocabulary."
  - "Kept generated schemas out of git via /schemas/*.schema.json and !/schemas/.gitkeep; schemas are reproducible build artifacts from Pydantic models."
  - "Translated Pydantic ValidationError into PersistedStateError at the persisted-state gate so graph and persistence code can catch a SagaSmith-owned exception."

patterns-established:
  - "Schema modules are leaf modules: they do not import services, graph, persistence, providers, or UI code."
  - "Every exported model inherits the same fail-closed SchemaModel configuration."
  - "Task-level TDD commits separate RED tests from GREEN implementations for traceability."

requirements-completed: [STATE-01, STATE-02, STATE-03, STATE-04, STATE-05]

duration: 8 min
completed: 2026-04-26
---

# Phase 1 Plan 02: Typed State Contracts and Schema Export Summary

**Strict Pydantic v2 runtime contracts with persisted-state validation and deterministic JSON Schema export for 16 SagaSmith boundary models.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-26T23:06:49Z
- **Completed:** 2026-04-26T23:14:56Z
- **Tasks:** 2/2 completed
- **Files modified:** 24 including this summary; 23 implementation/test/config files before summary

## Accomplishments

- Implemented fail-closed Pydantic v2 models for the first-slice state contract: player preferences, content policy, house rules, narrative/session state, memory packets, mechanics records, state deltas, canon conflicts, safety events, cost state, and compact `SagaState`.
- Added validators for `PlayerProfile.pillar_weights`, MVP-only `combat_style="theater_of_mind"`, `HouseRules.session_end_trigger`, `MemoryPacket.token_cap`, strict literal fields, and compact state references.
- Added `validate_persisted_state(data)` plus `PersistedStateError` so untrusted persisted JSON is rejected before graph consumption without downstream code catching Pydantic internals.
- Added `export_all_schemas(out_dir)` and `sagasmith schema export --out schemas` to write deterministic `.schema.json` files for all LLM-boundary and persisted models.
- Added 31 schema tests covering RED/GREEN behavior, round-trips, validation failures, compact references, deterministic export, CLI export, and project-owned error translation.

## Task Commits

Each task was committed atomically where possible:

1. **Task 1 RED: schema contract tests** - `82db307` (`test`)
2. **Task 1 GREEN: Pydantic state contracts** - `5652757` (`feat`)
3. **Task 2 RED: validation gate and export tests** - `f2be08e` (`test`)
4. **Task 2 GREEN: validation gate, exporter, and CLI** - `4e0f016` (`feat`)

**Plan metadata:** committed after self-check.

_Note: Both tasks were TDD, so each intentionally produced separate RED and GREEN commits._

## Files Created/Modified

- `src/sagasmith/schemas/common.py` - Shared `SchemaModel`, small value objects, token estimator, and key-validation helper.
- `src/sagasmith/schemas/enums.py` - Project enum vocabulary for phases, proficiency, deltas, checks, safety, pacing, combat style, dice UX, campaign length, character mode, death policy, and conflicts.
- `src/sagasmith/schemas/player.py` - `PlayerProfile`, `ContentPolicy`, and `HouseRules` contracts with onboarding validators.
- `src/sagasmith/schemas/narrative.py` - `SessionState`, `SceneBrief`, and token-bounded `MemoryPacket`.
- `src/sagasmith/schemas/mechanics.py` - `CharacterSheet`, `CombatState`, `CheckProposal`, `RollResult`, and `CheckResult`.
- `src/sagasmith/schemas/deltas.py` - `StateDelta` and `CanonConflict`.
- `src/sagasmith/schemas/safety_cost.py` - `SafetyEvent` and `CostState`.
- `src/sagasmith/schemas/saga_state.py` - Compact `SagaState` graph-state container using references and bounded payloads.
- `src/sagasmith/schemas/validation.py` - Persisted-state validation gate and project-owned exception.
- `src/sagasmith/schemas/export.py` - Deterministic JSON Schema exporter and 16-model export list.
- `src/sagasmith/schemas/__init__.py` - Public schema import surface for downstream code.
- `src/sagasmith/cli/schema_cmd.py` - Typer `schema export` subcommand.
- `src/sagasmith/cli/main.py` - Registers the `schema` subapp while preserving `version`.
- `.gitignore` - Ignores generated schema artifacts while keeping `schemas/.gitkeep` tracked.
- `schemas/.gitkeep` - Tracks the schema export output directory.
- `tests/schemas/*.py` - Unit and CLI tests for all schema contracts and export behavior.

## Exported Models

`export_all_schemas` and `sagasmith schema export` emit exactly these 16 model schemas:

1. `CanonConflict`
2. `CharacterSheet`
3. `CheckProposal`
4. `CheckResult`
5. `CombatState`
6. `ContentPolicy`
7. `CostState`
8. `HouseRules`
9. `MemoryPacket`
10. `PlayerProfile`
11. `RollResult`
12. `SafetyEvent`
13. `SagaState`
14. `SceneBrief`
15. `SessionState`
16. `StateDelta`

## Interpretation Choices

- `GameClock` uses `day`, `hour`, and `minute`, giving the first slice a compact status-panel clock and future duration hook without adding calendar complexity.
- `PacingTarget` uses `pillar`, `tension`, and `length`, matching the scene-planning examples while avoiding premature pacing taxonomies.
- `AttackProfile` uses `id`, `name`, `modifier`, `damage`, `traits`, and optional `range`, sufficient for the first level-1 martial PC and simple enemies.
- `Effect` is a typed human-readable effect (`kind`, `description`, optional `target_id`); deterministic rules plans can refine semantics without changing `CheckResult` shape.
- `MemoryPacket` estimates tokens as `ceil(len(text) / 4)`, implemented as `(len(text) + 3) // 4`, over `summary` plus `recent_turns`.
- Pydantic strict mode rejects float-to-int coercion (for example `RollResult.total=23.0`), so tests assert the stricter behavior.
- Field value constraints use `Literal[...]` for persisted JSON compatibility under strict Pydantic mode. The enum classes still exist in `schemas/enums.py` as the shared project vocabulary requested by the plan.

## Validation and Export Hooks for Plan 03

Plan 03 smoke/eval work should exercise:

- `sagasmith.schemas.validation.validate_persisted_state` for malformed persisted-state fixtures.
- `sagasmith.schemas.export.export_all_schemas` for schema artifact generation in a temp directory.
- `uv run sagasmith schema export --out schemas` for CLI-level no-paid-call smoke coverage.

## Verification

All plan verification commands passed:

- `uv run pytest tests/schemas/ -x -q` — passed (`31 passed`).
- `uv run ruff check src/sagasmith/schemas tests/schemas` — passed.
- `uv run pyright src/sagasmith/schemas` — passed (`0 errors, 0 warnings, 0 informations`).
- `uv run sagasmith schema export --out schemas` — passed and wrote 16 schema files.
- Schema count check — passed (`16`).
- `uv run python -c "from sagasmith.schemas import SagaState; print(SagaState.model_json_schema()['title'])"` — passed (`SagaState`).

Task acceptance gates also passed, including import-surface checks, compact-reference grep, CLI wiring grep, `.gitignore` schema artifact rules, JSON parsing of `schemas/SagaState.schema.json`, and Task 2's 11-test focused suite.

## Decisions Made

- Used `Literal[...]` for model fields whose persisted representation is a string literal, because `ConfigDict(strict=True)` rejects raw strings for enum-typed fields. Enum classes remain available as explicit project vocabulary.
- Kept JSON Schema files generated but ignored. This prevents checked-in artifact drift while preserving a tracked `schemas/` directory and deterministic export command.
- Converted Pydantic validation failures into `PersistedStateError` at the persistence/graph boundary, keeping downstream exception handling SagaSmith-owned.
- Treated `StateDelta.value` as the only intentional `Any`, matching the plan's opaque payload allowance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used string Literal fields instead of enum-typed model fields under strict mode**
- **Found during:** Task 1 (Model the schemas package)
- **Issue:** Pydantic strict mode does not coerce raw JSON strings into enum instances. Persisted state and test fixtures need JSON string values to validate directly.
- **Fix:** Kept the requested `StrEnum` classes in `schemas/enums.py`, but typed persisted model fields with `Literal[...]` where the JSON contract is string-valued.
- **Files modified:** `src/sagasmith/schemas/player.py`, `src/sagasmith/schemas/narrative.py`, `src/sagasmith/schemas/mechanics.py`, `src/sagasmith/schemas/deltas.py`, `src/sagasmith/schemas/safety_cost.py`, `src/sagasmith/schemas/saga_state.py`
- **Verification:** `uv run pytest tests/schemas/ -x`, `uv run pyright src/sagasmith/schemas`, and import-surface acceptance checks passed.
- **Committed in:** `5652757`

**2. [Rule 3 - Blocking] Added typed default factories and covariant key helper for pyright strictness**
- **Found during:** Task 1 verification
- **Issue:** Pyright reported unknown list element types for bare `Field(default_factory=list)` and a dict invariance error when checking pillar keys.
- **Fix:** Switched to typed default factories such as `list[CheckResult]` and changed the key helper to accept `Mapping[str, object]`.
- **Files modified:** `src/sagasmith/schemas/common.py`, `src/sagasmith/schemas/narrative.py`, `src/sagasmith/schemas/saga_state.py`
- **Verification:** `uv run pyright src/sagasmith/schemas` passed with `0 errors, 0 warnings, 0 informations`.
- **Committed in:** `5652757`

**3. [Rule 3 - Blocking] Adjusted shell verification syntax for Windows PowerShell**
- **Found during:** Task 2 verification
- **Issue:** The plan's POSIX `test -f` shell snippet is not valid in this Windows PowerShell environment.
- **Fix:** Used the PowerShell equivalent `Test-Path` while preserving the same acceptance condition.
- **Files modified:** None.
- **Verification:** Corrected Task 2 verification passed and all full-plan verification commands passed.
- **Committed in:** N/A (environment command adjustment only)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking issues)
**Impact on plan:** All deviations preserved the strict schema contract and Windows-compatible verification without expanding runtime scope.

## Issues Encountered

- Generated `schemas/*.schema.json` files were produced during verification but intentionally ignored by git per the plan. Only `schemas/.gitkeep` is tracked.
- No external services, API keys, or authentication gates were required.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Grep matches for `= None` and `=[]` in created schema files are intentional optional fields or local accumulator initialization, not UI-facing stubs or mock data sources.

## Threat Flags

None beyond the plan threat model. This plan introduced a persisted-state trust-boundary gate and a local schema export CLI, both explicitly covered by T-01-06 through T-01-10.

## TDD Gate Compliance

- RED gate commits exist: `82db307`, `f2be08e`.
- GREEN gate commits exist after RED: `5652757`, `4e0f016`.
- No separate refactor commit was needed; cleanup changes were included before each GREEN commit after verification.

## Next Phase Readiness

- Plan 03 can build no-paid-call smoke/eval checks on top of the implemented schema import surface, `validate_persisted_state`, `export_all_schemas`, and `sagasmith schema export`.
- Later deterministic services can import schema models from `sagasmith.schemas` without reaching into submodules.
- Provider/agent phases can use the exported JSON Schemas as the structured-output contract source.

## Self-Check: PASSED

- Confirmed key created files exist: all schema modules, validation/export modules, CLI schema command, `schemas/.gitkeep`, and all `tests/schemas/*.py` files.
- Confirmed all task commits exist: `82db307`, `5652757`, `f2be08e`, and `4e0f016`.
- Re-ran final plan verification commands successfully.
- Confirmed `SagaState.model_json_schema()['title']` returns `SagaState`.
- Confirmed working tree was clean before writing this summary except ignored generated schema artifacts.

---
*Phase: 01-contracts-scaffold-and-eval-spine*
*Completed: 2026-04-26*
