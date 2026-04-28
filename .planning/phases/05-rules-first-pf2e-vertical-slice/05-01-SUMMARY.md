---
phase: 05-rules-first-pf2e-vertical-slice
plan: 01
subsystem: rules
tags: [pf2e, dice, rules-engine, pydantic, tdd]

requires:
  - phase: 02-deterministic-trust-services
    provides: [DiceService, compute_degree, mechanics schemas]
  - phase: 04-graph-runtime-and-agent-skills
    provides: [RulesLawyer integration target for downstream graph wiring]
provides:
  - First-slice level-1 martial CharacterSheet factory
  - Typed weak melee and weak ranged first-slice enemy factories
  - Deterministic RulesEngine skill and Perception check resolution
affects: [phase-05-combat, phase-05-graph-wiring, phase-05-tui-sheet, QA-03]

tech-stack:
  added: []
  patterns: [pure rules data factories, frozen dataclass rules service, fail-closed stat lookup]

key-files:
  created:
    - src/sagasmith/rules/__init__.py
    - src/sagasmith/rules/first_slice.py
    - src/sagasmith/services/rules_engine.py
    - tests/rules/test_first_slice_data.py
    - tests/services/test_rules_engine.py
  modified:
    - src/sagasmith/schemas/common.py

key-decisions:
  - "RulesEngine rejects unsupported stats before rolling so untrusted player stat names cannot reach DiceService."
  - "CombatantState now carries optional first-slice enemy mechanics fields with backward-compatible defaults so enemy records validate as typed models instead of loose dictionaries."

patterns-established:
  - "TDD gate sequence: RED test commits precede GREEN implementation commits for each task."
  - "First-slice mechanics outputs are built only from CharacterSheet, DiceService, and compute_degree."

requirements-completed: [RULE-04, RULE-05, RULE-11, RULE-12, QA-03]

duration: 3 min
completed: 2026-04-28
---

# Phase 5 Plan 1: Deterministic First-Slice Rules Foundation Summary

**Typed PF2e first-slice character/enemy data plus deterministic skill and Perception check resolution with auditable DiceService roll IDs.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-28T11:05:49Z
- **Completed:** 2026-04-28T11:09:07Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `make_first_slice_character()` returning a validated level-1 Valeros-style martial `CharacterSheet` with pinned saves, trained skills, attacks, inventory, HP, AC, and perception.
- Added `make_first_slice_enemies()` returning two typed `CombatantState` enemy records with stable IDs, attacks, saves, perception modifiers, AC, HP, and XP values.
- Added frozen `RulesEngine` with `build_check_proposal()` and `resolve_check()` for skill and Perception checks through `DiceService.roll_d20()` and `compute_degree()`.
- Proved unsupported stats fail closed before any roll is attempted.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: First-slice data tests** - `4f0017d` (test)
2. **Task 1 GREEN: First-slice data helpers** - `6a3a48b` (feat)
3. **Task 2 RED: Rules engine tests** - `768ae91` (test)
4. **Task 2 GREEN: Rules engine resolution** - `a3fca3e` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/rules/__init__.py` - Exports first-slice rules data factory helpers.
- `src/sagasmith/rules/first_slice.py` - Defines the stable first-slice PC and two typed enemy records.
- `src/sagasmith/services/rules_engine.py` - Resolves deterministic skill and Perception checks with audit-ready results.
- `src/sagasmith/schemas/common.py` - Extends `CombatantState` with backward-compatible mechanics fields needed by first-slice enemies.
- `tests/rules/test_first_slice_data.py` - Covers sheet validation, pinned fields, attacks, trained skills, and typed enemies.
- `tests/services/test_rules_engine.py` - Covers deterministic check resolution, roll IDs, degree computation, proposals, and unsupported stat rejection.

## Decisions Made

- `RulesEngine` performs stat validation before rolling to satisfy the tampering mitigation in T-05-01.
- `CombatantState` was extended with defaulted first-slice enemy fields rather than returning dictionaries, preserving existing schema tests while enabling typed enemy records.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added first-slice enemy mechanics fields to `CombatantState`**
- **Found during:** Task 1 (Add first-slice character and enemy data helpers)
- **Issue:** The plan required first-slice enemies to validate as `CombatantState` values containing armor class, HP, perception, attacks, saves, and XP data, but the existing model only carried HP, AC, name, id, and conditions.
- **Fix:** Added backward-compatible defaulted fields for `level`, `perception_modifier`, `attacks`, `saving_throws`, and `xp_value` to `CombatantState`, then populated them in first-slice enemies.
- **Files modified:** `src/sagasmith/schemas/common.py`, `src/sagasmith/rules/first_slice.py`, `tests/rules/test_first_slice_data.py`
- **Verification:** `uv run pytest tests/rules/test_first_slice_data.py -q`; `uv run pytest tests/schemas/test_mechanics_models.py -q`; plan-level pyright passed.
- **Committed in:** `6a3a48b`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The auto-fix was required for typed enemy data correctness and kept existing callers compatible through defaults. No scope creep beyond first-slice mechanics data.

## Issues Encountered

None.

## TDD Gate Compliance

- Task 1 RED commit `4f0017d` preceded GREEN commit `6a3a48b`.
- Task 2 RED commit `768ae91` preceded GREEN commit `a3fca3e`.
- No refactor commits were needed.

## Known Stubs

None.

## Verification Results

- `uv run pytest tests/rules/test_first_slice_data.py -q` — PASS (3 passed)
- `uv run pytest tests/services/test_rules_engine.py -q` — PASS (4 passed)
- `uv run pytest tests/rules/test_first_slice_data.py tests/services/test_rules_engine.py -q` — PASS (7 passed)
- `uv run pytest tests/schemas/test_mechanics_models.py -q` — PASS (8 passed)
- `uv run pyright src/sagasmith/rules src/sagasmith/services/rules_engine.py tests/rules tests/services/test_rules_engine.py` — PASS (0 errors)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `05-02`: typed first-slice PC and enemy records now exist, and deterministic check resolution provides the DiceService/compute_degree pattern that combat can reuse for initiative and Strikes.

## Self-Check: PASSED

- Verified created files exist: `src/sagasmith/rules/__init__.py`, `src/sagasmith/rules/first_slice.py`, `src/sagasmith/services/rules_engine.py`, `tests/rules/test_first_slice_data.py`, `tests/services/test_rules_engine.py`, and this summary.
- Verified task commits exist: `4f0017d`, `6a3a48b`, `768ae91`, `a3fca3e`.

---
*Phase: 05-rules-first-pf2e-vertical-slice*
*Completed: 2026-04-28*
