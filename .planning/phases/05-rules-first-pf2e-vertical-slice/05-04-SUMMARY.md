---
phase: 05-rules-first-pf2e-vertical-slice
plan: 04
subsystem: tui
tags: [pf2e, textual, character-sheet, dice-overlay, combat-status, tdd]

requires:
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [first-slice CharacterSheet data, deterministic CheckResult and CombatState outputs, RulesLawyer graph state wiring]
provides:
  - Plain-text /sheet renderer using live graph CharacterSheet state before factory fallback
  - Reveal-mode dice detail and compact roll transcript renderers for CheckResult audit data
  - Combat-aware status panel text for active combatant, actions, reactions, positions, enemies, and last rolls
affects: [phase-05-vertical-slice-qa, phase-06-ai-gm-story-loop, tui-controls]

tech-stack:
  added: []
  patterns: [pure TUI text renderers, graph-state-first command rendering, public status snapshot formatter]

key-files:
  created:
    - src/sagasmith/tui/widgets/sheet.py
    - src/sagasmith/tui/widgets/dice_overlay.py
    - tests/tui/test_sheet_command.py
    - tests/tui/test_dice_overlay.py
    - tests/tui/test_combat_status.py
  modified:
    - src/sagasmith/tui/commands/control.py
    - src/sagasmith/tui/widgets/status_panel.py
    - src/sagasmith/tui/state.py

key-decisions:
  - "The `/sheet` command reads `graph_runtime.graph.get_state(...).values['character_sheet']` first and falls back to the first-slice factory only when live state is absent or invalid."
  - "Phase 5 reveal-mode dice UI is transcript-rendered from existing `CheckResult` values and intentionally omits modal pre-prompts/dismissal hints."
  - "Status panel formatting exposes typed combat state through a public formatter so tests and widgets share the same plain-text output."

patterns-established:
  - "TUI mechanics surfaces render from Pydantic mechanics models instead of narration text or UI-local identifiers."
  - "Combat status handles zero, one, and two enemies without assuming a fixed encounter template."

requirements-completed: [RULE-04, RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, TUI-07]

duration: 4 min
completed: 2026-04-28
---

# Phase 5 Plan 4: TUI Mechanics Surfaces Summary

**Live `/sheet` character rendering, reveal-mode roll audit text, and combat-aware status panel output for deterministic first-slice PF2e mechanics.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-28T11:23:49Z
- **Completed:** 2026-04-28T11:28:01Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Replaced the `/sheet` Phase 3 stub with a stable read-only character sheet renderer covering Identity, Durability, Perception and saves, Skills, Attacks, Inventory, and footer text.
- Ensured `/sheet` prefers live graph `character_sheet` data so current HP changes render correctly, while invalid or absent live sheets fall back to `make_first_slice_character()`.
- Added pure reveal-mode dice renderers that show DC, modifier, d20, total, degree, and persisted `roll_id` without generating a second roll.
- Extended status rendering with typed combat-state text for round, active combatant, actions, reaction, positions, enemy HP, and three last-roll summaries.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Sheet command tests** - `760d06a` (test)
2. **Task 1 GREEN: Live sheet renderer and /sheet command** - `0c9e05b` (feat)
3. **Task 2 RED: Reveal dice renderer tests** - `f504aa6` (test)
4. **Task 2 GREEN: Reveal dice audit renderers** - `d85b8c7` (feat)
5. **Task 3 RED: Combat status tests** - `0ec0b29` (test)
6. **Task 3 GREEN: Combat-aware status panel** - `d4b61d8` (feat)
7. **Verification fix: Pyright-clean public status formatter** - `991c4a4` (fix)

**Plan metadata:** pending final docs commit

_Note: TDD tasks produced RED and GREEN commits. A follow-up verification fix cleared plan-level pyright errors introduced by the new tests._

## Files Created/Modified

- `src/sagasmith/tui/widgets/sheet.py` - Renders stable plain-text `CharacterSheet` details for `/sheet`.
- `src/sagasmith/tui/commands/control.py` - Resolves live graph `character_sheet` data before fallback and writes rendered sheet lines to `NarrationArea`.
- `tests/tui/test_sheet_command.py` - Covers sheet headings, fallback behavior, and live `current_hp=13` rendering as `13/20`.
- `src/sagasmith/tui/widgets/dice_overlay.py` - Renders reveal-mode check details and compact `[roll]` audit lines from `CheckResult`.
- `tests/tui/test_dice_overlay.py` - Covers required reveal fields, exact compact line, and omitted Phase 5 modal prompts.
- `src/sagasmith/tui/widgets/status_panel.py` - Adds combat status and full snapshot formatting helpers used by the Textual widget.
- `src/sagasmith/tui/state.py` - Adds optional typed `combat_state` to `StatusSnapshot`.
- `tests/tui/test_combat_status.py` - Covers active combatant text, actions/reactions, positions, enemy count variants, defeated suffix, and last-roll limit.

## Decisions Made

- `/sheet` treats graph state as authoritative for current character state and validates dict data with `CharacterSheet.model_validate(...)` before rendering.
- Reveal-mode checks are rendered as transcript text in Phase 5, not a modal, because checks are already resolved and persisted before display.
- Status rendering uses typed `CombatState | None`; callers with dictionaries must validate before rendering rather than weakening renderer types.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cleared plan-level pyright failures from new tests**
- **Found during:** Plan-level verification after Task 3
- **Issue:** `tests/tui/test_combat_status.py` called protected `StatusPanel._format_snapshot(...)`, and `tests/tui/test_sheet_command.py` retained an unused import. Pyright failed even though tests passed.
- **Fix:** Added public `format_status_snapshot(snapshot: StatusSnapshot) -> str`, delegated the widget method to it, updated tests to use the public helper, and removed the unused import.
- **Files modified:** `src/sagasmith/tui/widgets/status_panel.py`, `tests/tui/test_combat_status.py`, `tests/tui/test_sheet_command.py`
- **Verification:** `uv run pytest tests/tui/test_sheet_command.py tests/tui/test_dice_overlay.py tests/tui/test_combat_status.py -q`; `uv run pyright src/sagasmith/tui tests/tui`
- **Committed in:** `991c4a4`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was required for plan-level type-check correctness and did not expand scope beyond the TUI renderer/test surfaces.

## Issues Encountered

- `gsd-sdk query` is unavailable in this environment (`gsd-sdk` only exposes `run`, `auto`, and `init`), so tracking artifacts were updated manually while preserving execute-plan semantics.

## TDD Gate Compliance

- Task 1 RED commit `760d06a` preceded GREEN commit `0c9e05b`.
- Task 2 RED commit `f504aa6` preceded GREEN commit `d85b8c7`.
- Task 3 RED commit `0ec0b29` preceded GREEN commit `d4b61d8`.
- Verification fix commit `991c4a4` followed GREEN after pyright exposed test typing issues.

## Known Stubs

None.

## Verification Results

- `uv run pytest tests/tui/test_sheet_command.py -q` — PASS (3 passed)
- `uv run pytest tests/tui/test_dice_overlay.py -q` — PASS (2 passed)
- `uv run pytest tests/tui/test_combat_status.py -q` — PASS (4 passed)
- `uv run pytest tests/tui/test_sheet_command.py tests/tui/test_dice_overlay.py tests/tui/test_combat_status.py -q` — PASS (9 passed)
- `uv run pyright src/sagasmith/tui tests/tui` — PASS (0 errors, 18 existing warnings)

## Acceptance Criteria Verification

- Task 1: `render_character_sheet(sheet: CharacterSheet) -> str` exists; `/sheet (stub` was removed from `control.py`; tests prove live HP `13/20` renders instead of factory `20/20`; required headings are asserted.
- Task 2: `render_reveal_check(...)` and `render_compact_roll_line(...)` exist; `dice_overlay.py` does not import `DiceService` or call `roll_d20`; tests assert `Saved to roll log:`, exact compact `[roll]` output, and omitted modal prompts/hints.
- Task 3: `format_combat_status(...)` exists; tests assert `Actions: 3/3`, `Reaction: available`, `Positions:`, only three last-roll entries, zero/one/two enemy renderings, and `(defeated)` suffix for an active combatant at 0 HP.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the plan threat model covered structured mechanics to TUI text, `/sheet` command data access, and roll audit identifiers.

## Next Phase Readiness

Ready for `05-05`: the TUI now exposes live sheet state, reveal-mode mechanics audit text, and combat status details needed by the no-paid-call vertical-slice integration and QA-03 verification gates.

## Self-Check: PASSED

- Verified created files exist: `src/sagasmith/tui/widgets/sheet.py`, `src/sagasmith/tui/widgets/dice_overlay.py`, `tests/tui/test_sheet_command.py`, `tests/tui/test_dice_overlay.py`, `tests/tui/test_combat_status.py`, and this summary.
- Verified task commits exist: `760d06a`, `0c9e05b`, `f504aa6`, `d85b8c7`, `0ec0b29`, `d4b61d8`, `991c4a4`.
- Verified final plan pytest and pyright checks pass.

---
*Phase: 05-rules-first-pf2e-vertical-slice*
*Completed: 2026-04-28*
