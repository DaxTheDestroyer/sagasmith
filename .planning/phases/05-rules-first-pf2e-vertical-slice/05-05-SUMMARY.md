---
phase: 05-rules-first-pf2e-vertical-slice
plan: 05
subsystem: rules-qa
tags: [pf2e, integration, evals, qa-03, textual, smoke]

requires:
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [first-slice rules data, CombatEngine, RulesLawyer graph wiring, TUI sheet and dice renderers]
provides:
  - End-to-end no-paid-call rules-first vertical-slice regression for /sheet, skill checks, reveal audit output, and simple combat
  - QA-03 scenario-driven mechanics coverage for PF2e degrees, seeded replay, skill checks, initiative, Strike, HP damage, and roll log completeness
  - Smoke harness registration for deterministic rules-first mechanics without provider calls
affects: [phase-06-ai-gm-story-loop, release-smoke, qa-gates]

tech-stack:
  added: []
  patterns: [Textual graph mechanics sync, scenario-driven QA gate tests, provider-free smoke harness checks]

key-files:
  created:
    - tests/integration/test_rules_first_vertical_slice.py
    - tests/evals/test_rules_first_qa_gate.py
  modified:
    - src/sagasmith/evals/harness.py
    - src/sagasmith/tui/app.py
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/services/combat_engine.py
    - src/sagasmith/tui/widgets/sheet.py
    - tests/services/test_combat_engine.py
    - tests/services/test_rules_engine.py

key-decisions:
  - "The vertical-slice TUI path now preserves prior graph mechanics state across sequential player inputs so combat can span multiple Textual submissions."
  - "QA-03 coverage is scenario-driven through deterministic services instead of a label-set assertion."
  - "The no-paid-call smoke harness includes a rules_first_vertical_slice check that constructs sheet, skill, initiative, and Strike mechanics without provider calls."

patterns-established:
  - "Integration tests verify persisted checkpoint state by reading LangGraph thread state after mechanics steps."
  - "Smoke harness checks append provider-free deterministic validations while preserving existing result conventions."

requirements-completed: [RULE-04, RULE-05, RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12, TUI-07, QA-03]

duration: 53 min
completed: 2026-04-28
---

# Phase 5 Plan 5: Rules-First Vertical Slice QA Summary

**No-paid-call PF2e vertical-slice regression covering live /sheet, reveal-mode skill checks, checkpoint-stable initiative, simple combat, and executable QA-03 mechanics gates.**

## Performance

- **Duration:** 53 min
- **Started:** 2026-04-28T11:29:41Z
- **Completed:** 2026-04-28T12:23:08Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added `test_rules_first_vertical_slice_sheet_check_reveal_and_combat`, which drives the Textual app through `/sheet`, `roll athletics dc 15`, `start combat`, `end turn` as needed, and `strike enemy_weak_melee with longsword` using fake/no-provider services.
- Verified checkpoint/resume auditability for initiative order, skill/initiative roll IDs, attack roll IDs, damage roll IDs, and persisted target HP after Strike resolution.
- Added named QA-03 tests that call `compute_degree`, `DiceService`, `RulesEngine`, and `CombatEngine` directly for each required mechanics scenario.
- Registered `rules_first_vertical_slice` in `run_smoke()` without OpenRouter or paid-provider usage.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Vertical-slice integration test** - `c108e71` (test)
2. **Task 1 GREEN: TUI/graph mechanics sync and persistent rules routing** - `fa58694` (feat)
3. **Task 2 RED: QA-03 mechanics gate tests** - `d184292` (test)
4. **Task 2 GREEN: Rules-first smoke harness check** - `41dcc32` (feat)
5. **Verification fix: Full lint cleanup** - `d031b3e` (fix)

**Plan metadata:** pending final docs commit

_Note: TDD tasks produced RED and GREEN commits. The final fix commit cleared plan-level lint verification after the full `src tests` check exposed formatting and SIM105 issues._

## Files Created/Modified

- `tests/integration/test_rules_first_vertical_slice.py` - End-to-end no-paid-call Textual/graph rules-first regression with checkpoint/resume assertions.
- `tests/evals/test_rules_first_qa_gate.py` - Scenario-driven QA-03 mechanics gate covering degree math, replay, skill checks, initiative, Strikes, HP damage, roll IDs, and smoke registration.
- `src/sagasmith/evals/harness.py` - Adds the `rules_first_vertical_slice` smoke check using deterministic rules services only.
- `src/sagasmith/tui/app.py` - Preserves mechanics graph state across sequential inputs and renders newly resolved checks, reveal audit details, effects, and combat status.
- `src/sagasmith/graph/runtime.py` - Adds `rules_lawyer` to the persistent graph START routing map so combat-phase persisted runtime invocations can execute.
- `src/sagasmith/services/combat_engine.py` - Ruff import formatting only.
- `src/sagasmith/tui/widgets/sheet.py` - Ruff whitespace formatting only.
- `tests/services/test_combat_engine.py` - Ruff whitespace formatting only.
- `tests/services/test_rules_engine.py` - Ruff whitespace formatting only.

## Decisions Made

- Sequential Textual inputs now carry forward graph `character_sheet`, `combat_state`, `check_results`, `state_deltas`, and `pending_narration` so the first-slice combat path can span multiple player submissions.
- The QA gate proves behavior by named scenario tests that call deterministic services directly, avoiding a brittle hardcoded coverage-label set.
- The smoke harness check reports deterministic roll IDs in its detail string, enough for smoke diagnostics without persisting or exposing secrets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added TUI graph mechanics synchronization for sequential rules inputs**
- **Found during:** Task 1 (vertical-slice integration test GREEN)
- **Issue:** The existing TUI input path invoked the graph for a single turn but did not render new `CheckResult` audit output, refresh combat status, or carry prior `combat_state` into the next rules input. The planned vertical slice could not observe reveal roll details or continue from `start combat` to `end turn`/`strike`.
- **Fix:** Added graph-state preservation in `_build_play_state(...)` and `_sync_mechanics_from_graph()` to render compact/reveal check output, effects, and typed combat status from deterministic graph state.
- **Files modified:** `src/sagasmith/tui/app.py`
- **Verification:** `uv run pytest tests/integration/test_rules_first_vertical_slice.py -q`; final plan pytest passed.
- **Committed in:** `fa58694`

**2. [Rule 3 - Blocking] Added persistent graph route mapping for combat-phase RulesLawyer starts**
- **Found during:** Task 1 (vertical-slice integration test GREEN)
- **Issue:** `build_persistent_graph(...)` did not include `rules_lawyer` in its START conditional-edge map, even though Phase 5 combat routing can return `rules_lawyer`.
- **Fix:** Added `"rules_lawyer": "rules_lawyer"` to the persistent graph route map.
- **Files modified:** `src/sagasmith/graph/runtime.py`
- **Verification:** `uv run pytest tests/integration/test_rules_first_vertical_slice.py -q`; final plan pytest passed.
- **Committed in:** `fa58694`

**3. [Rule 3 - Blocking] Cleared lint issues required by plan-level verification**
- **Found during:** Plan-level `uv run ruff check src tests && uv run pyright src tests`
- **Issue:** Ruff reported import/whitespace formatting in existing Phase 5 files and a SIM105 issue in the new TUI status sync helper.
- **Fix:** Applied ruff-safe import/whitespace cleanup and replaced the `try/except/pass` status update guard with `contextlib.suppress(Exception)`.
- **Files modified:** `src/sagasmith/tui/app.py`, `tests/integration/test_rules_first_vertical_slice.py`, `src/sagasmith/services/combat_engine.py`, `src/sagasmith/tui/widgets/sheet.py`, `tests/services/test_combat_engine.py`, `tests/services/test_rules_engine.py`
- **Verification:** `uv run ruff check src tests && uv run pyright src tests` — PASS (0 pyright errors, existing warnings only)
- **Committed in:** `d031b3e`

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 blocking)
**Impact on plan:** All fixes were required for the planned no-paid-call vertical-slice and full verification gates. No scope expanded beyond deterministic first-slice mechanics, TUI rendering, and verification hygiene.

## Issues Encountered

- `gsd-sdk query` is unavailable in this environment (`gsd-sdk` only exposes `run`, `auto`, and `init`), so tracking artifacts were updated manually while preserving execute-plan semantics.
- `uv run pyright src tests` passes with 0 errors and existing warning volume; warnings are pre-existing type strictness warnings outside this plan's scope.

## TDD Gate Compliance

- Task 1 RED commit `c108e71` preceded GREEN commit `fa58694`.
- Task 2 RED commit `d184292` preceded GREEN commit `41dcc32`.
- Verification fix commit `d031b3e` followed the GREEN commits after full lint/type verification.

## Known Stubs

None.

## Verification Results

- `uv run pytest tests/integration/test_rules_first_vertical_slice.py -q` — PASS (1 passed)
- `uv run pytest tests/evals/test_rules_first_qa_gate.py -q` — PASS (7 passed)
- `uv run pytest tests/evals/test_rules_first_qa_gate.py tests/integration/test_rules_first_vertical_slice.py -q` — PASS (8 passed)
- `uv run ruff check src tests && uv run pyright src tests` — PASS (ruff clean; pyright 0 errors, existing warnings)

## Acceptance Criteria Verification

- Task 1: `tests/integration/test_rules_first_vertical_slice.py` contains `test_rules_first_vertical_slice_sheet_check_reveal_and_combat`, `roll athletics dc 15`, `start combat`, `end turn`, and `strike enemy_weak_melee with longsword`; asserts `damage_roll=roll_`, unchanged `initiative_order`, post-Strike attack/damage roll IDs, target HP preservation, and contains no `OpenRouterClient`.
- Task 2: `tests/evals/test_rules_first_qa_gate.py` contains `test_qa03_degree_boundaries`, `test_qa03_seeded_replay`, `test_qa03_skill_check`, `test_qa03_initiative`, `test_qa03_strike_and_hp_damage`, and `test_qa03_roll_log_completeness`; each calls deterministic services/functions rather than asserting a hardcoded label set.
- Task 2: `src/sagasmith/evals/harness.py` contains `rules_first_vertical_slice`, and `uv run pytest tests/evals/test_rules_first_qa_gate.py -q` exits 0.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the plan threat model covered no-provider verification, persisted/rendered mechanics auditability, and smoke harness registration. No new network endpoints, auth paths, file access boundaries, or schema trust boundaries were introduced.

## Next Phase Readiness

Phase 5 is complete and ready for phase verification: the rules-first PF2e vertical slice now has deterministic unit, TUI, graph, integration, smoke, and QA-03 coverage proving that first-slice mechanics do not require LLM-authored math.

## Self-Check: PASSED

- Verified created files exist: `tests/integration/test_rules_first_vertical_slice.py`, `tests/evals/test_rules_first_qa_gate.py`, and this summary.
- Verified task commits exist: `c108e71`, `fa58694`, `d184292`, `41dcc32`, `d031b3e`.
- Verified final plan pytest, ruff, and pyright checks pass.

---
*Phase: 05-rules-first-pf2e-vertical-slice*
*Completed: 2026-04-28*
