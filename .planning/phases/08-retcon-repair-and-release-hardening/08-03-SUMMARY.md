---
phase: 08-retcon-repair-and-release-hardening
plan: 03
subsystem: tui
tags: [retcon, tui, commands, confirmation, sync]

requires:
  - phase: 08-retcon-repair-and-release-hardening
    provides: RetconService preview/confirm, GraphRuntime preview_retcon/confirm_retcon, checkpoint rewind, derived rebuild/sync
provides:
  - TUI /retcon picker with recent eligible completed turn candidates
  - Deterministic preview rendering with affected turns, vault outputs, effects, and typed-confirmation instruction
  - Turn-specific typed confirmation via RETCON {turn_id} token with blocked guidance for wrong tokens
  - Post-retcon sync_after_retcon() resyncs narration and mechanics without exiting the app
affects: [phase-8-release-gate, canonical-memory, vault-repair]

tech-stack:
  added: []
  patterns:
    - RetconCommand delegates to RetconService via GraphRuntime entrypoints for preview/confirm
    - Confirmation tokens are turn-specific ("RETCON {turn_id}") requiring exact match
    - sync_after_retcon() wraps _sync_narration_from_graph and _sync_mechanics_from_graph in suppress blocks

key-files:
  created:
    - tests/tui/test_retcon_command.py
  modified:
    - src/sagasmith/tui/commands/control.py
    - src/sagasmith/tui/app.py
    - tests/tui/test_control_commands.py
    - tests/tui/test_commands_post_interrupts.py

key-decisions:
  - "/retcon no-arg lists recent eligible completed turns; never silently targets latest turn."
  - "Preview includes [system] /retcon candidates: or [system] /retcon preview for {turn_id}: with deterministic formatting."
  - "Confirmation uses exact turn-specific token 'RETCON {turn_id}' parsed from joined command args."
  - "sync_after_retcon() is added to SagaSmithApp and called after successful confirm_retcon to resync narration and mechanics."
  - "Both success and blocked messages restrict output to turn ids/counts and repair guidance, never removed transcript content."

patterns-established:
  - "RetconCommand.handle() splits args into turn_id + confirmation_tokens; no-arg lists candidates, single-arg previews, multi-arg confirms."
  - "Blocked retcon prints [system] /retcon blocked: {message} and [system] repair: {repair_guidance} side by side."

requirements-completed: [QA-01, QA-02]

duration: 12min
completed: 2026-04-29
---

# Phase 8 Plan 03: Retcon TUI Picker, Preview, and Confirmation Summary

**TUI /retcon command with candidate picker, deterministic preview, turn-specific typed confirmation, and post-retcon resync — replacing the Phase 4 interrupt-posting stub.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-29T17:23:30Z
- **Completed:** 2026-04-29T17:35:00Z
- **Tasks:** 2 completed (4 TDD commits)
- **Files modified:** 5

## Accomplishments

- Replaced the Phase 4 `/retcon` stub with a full picker/preview/confirmation flow delegating to `RetconService` through `GraphRuntime`.
- `/retcon` no-arg lists recent eligible completed turns with deterministic `[system] /retcon candidates:` output.
- `/retcon <turn_id>` displays preview with affected turns, vault outputs, effects, and `Type: /retcon {turn_id} RETCON {turn_id}` instruction.
- `/retcon <turn_id> RETCON <turn_id>` confirms rollback with exact turn-specific token; wrong token prints blocked guidance.
- Added `SagaSmithApp.sync_after_retcon()` that resyncs narration and mechanics after successful retcon without exiting.
- All messages restrict output to turn ids/counts and repair guidance — never removed transcript content.

## Task Commits

1. **Task 1 RED: Add failing retcon picker/preview tests** — `a715205` (test)
2. **Task 1 GREEN: Implement retcon picker and preview rendering** — `437ac42` (feat)
3. **Task 2 RED: Add failing retcon confirmation and sync tests** — `90a7a9e` (test)
4. **Task 2 GREEN: Implement retcon typed confirmation and sync-after-retcon** — `91611d9` (feat)
5. **Ruff import fix** — `a79cd35` (style)

## Files Created/Modified

- `tests/tui/test_retcon_command.py` — 8 tests covering no-graph-unavailable, candidate listing, preview, blocked preview, correct-token confirm, wrong-token blocked, sync-after-retcon, and transcript-exclusion assertions.
- `src/sagasmith/tui/commands/control.py` — RetconCommand.handle() rewritten from Phase 4 interrupt stub to full picker/preview/confirmation flow using RetconService.
- `src/sagasmith/tui/app.py` — Added sync_after_retcon() method that wraps _sync_narration_from_graph and _sync_mechanics_from_graph in suppress blocks.
- `tests/tui/test_control_commands.py` — Removed RetconCommand from _STUB_CASES (no longer a stub).
- `tests/tui/test_commands_post_interrupts.py` — Removed RetconCommand registration and stale interrupt-posting test; retcon no longer uses graph interrupts.

## Decisions Made

- `/retcon` no-arg lists recent eligible completed turns; never silently targets latest turn (D-01).
- Preview shows affected turn ids/effects before confirmation; confirmation requires turn-specific token (D-05, D-06, D-07).
- After successful retcon, sync_after_retcon() resyncs narration and mechanics without requiring session exit (D-08).
- Both success and blocked messages never expose removed transcript content (T-08-10, D-12).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated existing stub tests for RetconCommand behavior change**
- **Found during:** Task 1 GREEN implementation
- **Issue:** `test_control_commands.py` expected `/retcon` to be a stub with "Phase 8" text; `test_commands_post_interrupts.py` expected `/retcon` to post `InterruptKind.RETCON`.
- **Fix:** Removed RetconCommand from `_STUB_CASES` and removed stale interrupt-posting test. Phase 8 retcon now uses RetconService, not graph interrupts.
- **Files modified:** `tests/tui/test_control_commands.py`, `tests/tui/test_commands_post_interrupts.py`
- **Verification:** `uv run pytest tests/tui/test_control_commands.py tests/tui/test_commands_post_interrupts.py` — 12 passed.
- **Committed in:** `437ac42`

**2. [Rule 3 - Blocking] Ruff unused import in test file**
- **Found during:** Pre-summary lint verification
- **Issue:** `unittest.mock.MagicMock` imported but unused in `test_retcon_command.py`.
- **Fix:** Removed the unused import.
- **Files modified:** `tests/tui/test_retcon_command.py`
- **Committed in:** `a79cd35`

---

**Total deviations:** 2 auto-fixed (2 blocking/tooling).
**Impact on plan:** Both fixes required for correctness and quality gates. No scope change.

## Known Stubs

None.

## Threat Flags

None beyond the planned retcon confirmation parsing and message-safety surfaces in the plan threat model.

## Issues Encountered

- The `_RecordingRuntime` test fake needed `db_conn` added for candidate-listing test (no-arg `/retcon` accesses `RetconService` through `app.graph_runtime.db_conn`). Resolved by adding optional `db_conn` parameter.

## User Setup Required

None — no external service configuration required.

## Verification

- `uv run pytest tests/tui/test_retcon_command.py tests/integration/test_narration_recovery.py tests/integration/test_retcon_runtime.py -x` — 27 passed.
- `uv run pytest tests/tui/test_retcon_command.py tests/tui/test_control_commands.py tests/tui/test_commands_post_interrupts.py tests/integration/test_narration_recovery.py tests/integration/test_retcon_runtime.py -x` — 40 passed.
- `uv run ruff check src/sagasmith/tui/commands/control.py src/sagasmith/tui/app.py tests/tui/test_retcon_command.py` — passed.

## Next Phase Readiness

- Phase 08-03 completes the retcon feature. All three Phase 8 plans (08-01, 08-02, 08-03, 08-04) are now complete.
- No blockers.

## Self-Check: PASSED

- Created tests exist: `tests/tui/test_retcon_command.py`.
- Modified source exists: `src/sagasmith/tui/commands/control.py`.
- Modified app exists: `src/sagasmith/tui/app.py`.
- Task commits found: `a715205`, `437ac42`, `90a7a9e`, `91611d9`, `a79cd35`.
- All 40 tests pass.

---
*Phase: 08-retcon-repair-and-release-hardening*
*Completed: 2026-04-29*
