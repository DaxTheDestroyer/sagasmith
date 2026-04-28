---
phase: 05-rules-first-pf2e-vertical-slice
plan: 02
subsystem: rules
tags: [pf2e, combat, dice, rules-engine, tdd]

requires:
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [first-slice character and enemy data, deterministic RulesEngine check resolution]
provides:
  - Deterministic first-slice CombatEngine for initiative, action economy, positions, Strikes, HP deltas, turn advancement, and encounter completion
  - Auditable attack and damage roll outputs for Strike resolution
  - Seeded d8 and d6 DiceService replay coverage
affects: [phase-05-graph-wiring, phase-05-tui-combat-status, phase-05-qa-vertical-slice]

tech-stack:
  added: []
  patterns: [frozen dataclass combat service, tuple-returned audit rolls, fail-closed first-slice targeting validation]

key-files:
  created:
    - src/sagasmith/services/combat_engine.py
    - tests/services/test_combat_engine.py
  modified:
    - tests/services/test_dice.py

key-decisions:
  - "CombatEngine returns both the Strike CheckResult and optional damage RollResult so downstream roll-log persistence can store exactly one damage roll_id per damaging Strike."
  - "First-slice melee targeting validates the target position tag and fails closed before action consumption or rolling."

patterns-established:
  - "Combat mechanics consume actions only after validating actor, target, attack, position, and remaining actions."
  - "Critical Strike damage rolls once, then doubles the RollResult total for the HP delta while preserving a single damage roll audit record."

requirements-completed: [RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12, QA-03]

duration: 4 min
completed: 2026-04-28
---

# Phase 5 Plan 2: First-Slice Combat Engine Summary

**Deterministic PF2e first-slice combat engine with auditable initiative, action economy, theater-of-mind positions, Strike damage rolls, HP deltas, and encounter completion.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-28T11:11:08Z
- **Completed:** 2026-04-28T11:15:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `CombatEngine.start_encounter()` to validate first-slice enemy limits, roll initiative deterministically, sort ties by total/perception/id, and initialize `CombatState` with actions, reactions, and valid position tags.
- Added `resolve_strike()`, `move()`, `end_turn()`, and `is_encounter_complete()` for deterministic theater-of-mind combat progression.
- Added Strike audit behavior: attack `CheckResult`, optional damage `RollResult`, HP `Effect`, and replayable `StateDelta` for damaging hits.
- Extended DiceService tests to prove seeded replay for `d8` and `d6` damage dice.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Combat setup tests** - `79583c1` (test)
2. **Task 1 GREEN: Encounter setup implementation** - `5420043` (feat)
3. **Task 2 RED: Combat action tests** - `07612c3` (test)
4. **Task 2 GREEN: Strike, movement, turns, and completion** - `22dc4f5` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/services/combat_engine.py` - New deterministic combat service for first-slice encounter setup, Strikes, movement, turn advancement, and completion checks.
- `tests/services/test_combat_engine.py` - Covers initiative setup, enemy validation, tie-breaking, hit/miss/critical hit, HP clamping, range validation, movement validation, turn skipping, reaction reset, and completion.
- `tests/services/test_dice.py` - Adds seeded replay coverage for `d8` and `d6` damage rolls.

## Decisions Made

- Strike resolution returns `tuple[CombatState, CheckResult, RollResult | None]` to make damage roll-log persistence explicit for downstream graph/TUI plans.
- Critical hit damage uses one damage roll and doubles the rolled total, preserving a single underlying damage `roll_id` as required by the plan.
- First-slice combat uses position tags only; no tactical grid, coordinates, MAP, reactions, or expanded actions were added.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `gsd-sdk query` is unavailable in this environment (`gsd-sdk` only exposes `run`, `auto`, and `init`), so tracking artifacts were updated manually while preserving the execute-plan semantics.

## TDD Gate Compliance

- Task 1 RED commit `79583c1` preceded GREEN commit `5420043`.
- Task 2 RED commit `07612c3` preceded GREEN commit `22dc4f5`.
- No refactor commits were needed.

## Known Stubs

None.

## Verification Results

- `uv run pytest tests/services/test_combat_engine.py::test_start_encounter_rolls_initiative_and_sets_action_state -q` — PASS (1 passed)
- `uv run pytest tests/services/test_combat_engine.py -q` — PASS (4 passed after Task 1)
- `uv run pytest tests/services/test_dice.py tests/services/test_combat_engine.py -q` — PASS (19 passed)
- `uv run pyright src/sagasmith/services/dice.py src/sagasmith/services/combat_engine.py tests/services/test_dice.py tests/services/test_combat_engine.py` — PASS (0 errors)

## Acceptance Criteria Verification

- Task 1: `start_encounter`, two-enemy guard, all action counts at `3`, approved position tag subset, and initiative tie-break tests verified.
- Task 2: `resolve_strike`, `move`, `end_turn`, and `is_encounter_complete` exist; tests verify hit/miss/critical hit, HP clamp at 0, invalid melee range text, damage roll IDs in effects, single-roll critical doubling, same-position movement rejection without action loss, defeated-combatant skip, and reaction reset.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the plan threat model already covered player action intent validation, state delta integrity, encounter setup limits, and combat roll auditability.

## Next Phase Readiness

Ready for `05-03`: deterministic combat mechanics now expose typed `CombatState`, `CheckResult`, `RollResult`, `Effect`, and `StateDelta` data for RulesLawyer graph routing and roll-log audit output.

## Self-Check: PASSED

- Verified created files exist: `src/sagasmith/services/combat_engine.py`, `tests/services/test_combat_engine.py`, and this summary.
- Verified task commits exist: `79583c1`, `5420043`, `07612c3`, `22dc4f5`.

---
*Phase: 05-rules-first-pf2e-vertical-slice*
*Completed: 2026-04-28*
