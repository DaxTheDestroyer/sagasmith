---
phase: 03-cli-setup-onboarding-and-tui-controls
plan: 02
subsystem: onboarding
tags: [pydantic, sqlite, wizard, state-machine, onboarding, pure-domain]

# Dependency graph
requires:
  - phase: 03-cli-setup-onboarding-and-tui-controls
    provides: campaigns(campaign_id) table via 0002_campaign_and_settings.sql (Plan 03-01)
provides:
  - OnboardingWizard: 9-phase state machine (pure domain, no I/O)
  - ONBOARDING_PHASES catalog + parse_answer() with 8 PromptFieldKind branches
  - OnboardingStore: atomic SQLite persistence for PlayerProfile/ContentPolicy/HouseRules
  - Migration 0003_onboarding_records.sql: three onboarding tables with FK to campaigns
  - Re-run support (ONBD-05): INSERT OR REPLACE semantics in OnboardingStore.commit()
  - 50 unit tests covering ONBD-01 through ONBD-05
affects:
  - 03-03-PLAN.md (TUI shell drives OnboardingWizard.step() with Textual screens)
  - 03-04-PLAN.md (/settings calls OnboardingStore.reload() to restart wizard)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - StrEnum used for OnboardingPhase and PromptFieldKind (UP042 StrEnum upgrade)
    - parse_answer() dispatch pattern: one branch per PromptFieldKind, returns (value, errors)
    - PILLAR_BUDGET normalization: int[0..10] → float[0..1] (sum check at wizard + Pydantic level)
    - SQLite 'with conn:' implicit transaction for atomic three-table INSERT OR REPLACE
    - BrokenContentPolicy subclass pattern for testing transaction atomicity

key-files:
  created:
    - src/sagasmith/onboarding/__init__.py
    - src/sagasmith/onboarding/prompts.py
    - src/sagasmith/onboarding/wizard.py
    - src/sagasmith/onboarding/store.py
    - src/sagasmith/persistence/migrations/0003_onboarding_records.sql
    - tests/onboarding/__init__.py
    - tests/onboarding/fixtures.py
    - tests/onboarding/test_prompts.py
    - tests/onboarding/test_wizard.py
    - tests/onboarding/test_store.py
  modified:
    - tests/persistence/test_migrations.py (v3 migration counts)
    - tests/persistence/test_campaign_settings_schema.py (v3 migration counts)
    - tests/app/test_campaign.py (schema_version == 3)

key-decisions:
  - "StrEnum used for OnboardingPhase/PromptFieldKind (ruff UP042 fix, Python 3.11+ StrEnum)"
  - "PILLAR_BUDGET parse_answer() rejects bool inputs to prevent True/False being treated as 1/0"
  - "BrokenContentPolicy subclass used for atomicity test — sqlite3.Connection.execute is read-only in CPython, cannot be patched via unittest.mock.patch.object"
  - "model_construct() used to bypass Pydantic validation when building broken test object"
  - "Three separate onboarding tables (not one JSON blob) per plan spec — each maps to a distinct Pydantic model lifecycle"

patterns-established:
  - "parse_answer() dispatch: one branch per PromptFieldKind enum value, returns (parsed_value, errors)"
  - "Wizard state machine: _DraftState accumulates parsed answers; step() validates before writing"
  - "edit() validates by re-constructing the affected Pydantic model; rolls back draft on error"
  - "SQLite 'with conn:' context manager for three-table atomic commit"

requirements-completed:
  - ONBD-01
  - ONBD-02
  - ONBD-03
  - ONBD-04
  - ONBD-05

# Metrics
duration: 12min
completed: 2026-04-27
---

# Phase 3 Plan 02: Onboarding Wizard Domain + SQLite Store Summary

**OnboardingWizard 9-phase state machine with parse_answer() for 8 field kinds, Pydantic-validated PlayerProfile/ContentPolicy/HouseRules triple, and atomic OnboardingStore with INSERT OR REPLACE re-run support — zero CLI/TUI imports, 50 tests.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-27T14:45:49Z
- **Completed:** 2026-04-27T14:57:26Z
- **Tasks:** 2 completed
- **Files modified:** 13

## Accomplishments

- `OnboardingWizard` drives the 9-phase onboarding interview (GAME_SPEC §7.1) with no I/O — pure state transitions with `step()`, `review()`, `edit()`, and `build_records()`
- `parse_answer()` handles 8 `PromptFieldKind` variants including PILLAR_BUDGET normalization, SOFT_LIMIT_MAP disposition validation, and lenient BOOL parsing
- `edit()` blocks `profile.combat_style` (MVP Literal constraint) and re-validates via Pydantic on all other paths
- `OnboardingStore` commits the three-model triple atomically via SQLite `with conn:` context, with `INSERT OR REPLACE` for re-run support (ONBD-05)
- Migration `0003_onboarding_records.sql` introduces three FK-enforced tables; schema reaches v3
- 50 unit tests covering all ONBD requirements, atomicity invariants, FK enforcement, and partial-state detection

## Task Commits

Each task was committed atomically:

1. **Task 1: Phase prompt catalog + wizard state machine + answer validation** - `9dd6e7e` (feat)
2. **Task 2: Onboarding SQLite store + migration 0003 + re-run (ONBD-05) support** - `bd00f29` (feat)

## Files Created/Modified

- `src/sagasmith/onboarding/__init__.py` — Package init exporting wizard, store, and prompt types
- `src/sagasmith/onboarding/prompts.py` — ONBOARDING_PHASES catalog, PromptField/PhasePrompt dataclasses, parse_answer() with 8 branches
- `src/sagasmith/onboarding/wizard.py` — OnboardingWizard state machine, _DraftState, StepResult
- `src/sagasmith/onboarding/store.py` — OnboardingStore frozen dataclass, OnboardingTriple value object
- `src/sagasmith/persistence/migrations/0003_onboarding_records.sql` — Three onboarding tables with FK to campaigns
- `tests/onboarding/fixtures.py` — make_happy_path_answers() returning 9-dict happy-path run
- `tests/onboarding/test_prompts.py` — parse_answer() and ONBOARDING_PHASES tests
- `tests/onboarding/test_wizard.py` — Wizard state machine tests including edit/review/build_records
- `tests/onboarding/test_store.py` — OnboardingStore tests (commit, reload, exists, atomicity, FK, re-run)
- `tests/persistence/test_migrations.py` — Updated for v3 migration count
- `tests/persistence/test_campaign_settings_schema.py` — Updated for v3 migration count
- `tests/app/test_campaign.py` — Updated for schema_version == 3

## Decisions Made

- Used `StrEnum` (ruff UP042 fix) for `OnboardingPhase` and `PromptFieldKind` — Python 3.12 project, no compatibility concern
- `BrokenContentPolicy` subclass pattern for atomicity test — CPython's `sqlite3.Connection.execute` is a read-only C slot, cannot be patched via `unittest.mock.patch.object`; `model_construct()` used to bypass Pydantic validation for the broken object
- Three separate onboarding tables per plan spec — each maps to a distinct Pydantic model with its own validation lifecycle
- `PILLAR_BUDGET` parser rejects `bool` inputs explicitly to prevent `True`/`False` being coerced to 1/0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing tests had hardcoded migration count v2**
- **Found during:** Task 2 (full test suite run after adding migration 0003)
- **Issue:** `tests/persistence/test_migrations.py` expected `[1, 2]` and `schema_version == 2`; `tests/persistence/test_campaign_settings_schema.py` expected `[1, 2]`; `tests/app/test_campaign.py` expected `schema_version == 2` — all now incorrect after adding migration v3
- **Fix:** Updated all hardcoded values to reflect v3 schema (`[1, 2, 3]`, `schema_version == 3`)
- **Files modified:** `tests/persistence/test_migrations.py`, `tests/persistence/test_campaign_settings_schema.py`, `tests/app/test_campaign.py`
- **Verification:** `uv run pytest -q` → 240 passed, 1 skipped
- **Committed in:** `bd00f29` (Task 2 commit)

**2. [Rule 3 - Blocking] sqlite3.Connection.execute is read-only; patch.object fails**
- **Found during:** Task 2 (atomicity test)
- **Issue:** Plan specified "monkeypatch `model_dump_json` to raise on second call" — CPython C extension objects have read-only attributes that `unittest.mock.patch.object` cannot replace
- **Fix:** Used `BrokenContentPolicy(ContentPolicy)` subclass with `model_construct()` to bypass Pydantic validation, injecting a broken triple that raises on serialization
- **Files modified:** `tests/onboarding/test_store.py`
- **Verification:** `test_commit_is_atomic_on_validation_failure` passes; profile row is absent after failure
- **Committed in:** `bd00f29` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 - Bug, 1 Rule 3 - Blocking)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep. All plan success criteria met.

## Issues Encountered

None — all tests pass, all verification commands clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `OnboardingWizard.step()` is ready for Plan 03-03 (TUI shell) to drive with Textual screens
- `OnboardingStore.reload()` is ready for Plan 03-04 (`/settings`) to restart wizard without destroying campaign
- Migration 0003 applies cleanly after 0002 via `apply_migrations`; schema v3 stable
- All ONBD-01 through ONBD-05 requirements met and test-verified
- No Textual/CLI imports in wizard.py or prompts.py; pure domain units remain isolated

---
*Phase: 03-cli-setup-onboarding-and-tui-controls*
*Completed: 2026-04-27*

## Self-Check: PASSED

- `src/sagasmith/onboarding/wizard.py` — FOUND
- `src/sagasmith/onboarding/prompts.py` — FOUND
- `src/sagasmith/onboarding/store.py` — FOUND
- `src/sagasmith/persistence/migrations/0003_onboarding_records.sql` — FOUND
- `tests/onboarding/test_prompts.py` — FOUND
- `tests/onboarding/test_wizard.py` — FOUND
- `tests/onboarding/test_store.py` — FOUND
- Task 1 commit `9dd6e7e` — FOUND in git log
- Task 2 commit `bd00f29` — FOUND in git log
