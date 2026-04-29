---
phase: 07-memory-vault-and-resume
plan: 05
subsystem: memory-vault
tags: [vault-sync, player-vault, recap, cli, tui, resume]

requires:
  - phase: 07-memory-vault-and-resume
    provides: [vault foundation, turn-close sync warning column, FTS5 and graph rebuild functions, rolling summary skill]
provides:
  - spoiler-safe player-vault projection with GM-only page skipping, foreshadow stubs, GM field/comment stripping, and regenerated index/log
  - `/recap` command rendering rolling summary plus recent transcript rows without provider calls
  - `ttrpg vault rebuild` and `ttrpg vault sync` repair commands
  - resumed session number increment and TUI vault-sync warning status display
affects: [07-06-qa, 08-retcon-repair, cli, tui, persistence]

tech-stack:
  added: []
  patterns:
    - TDD red/green commits for projection and recap behavior
    - derived vault layers remain rebuildable from master-vault markdown

key-files:
  created:
    - src/sagasmith/cli/vault_cmd.py
    - tests/vault/test_sync.py
    - tests/cli/test_vault_cmd.py
    - tests/tui/test_resume_and_vault_warning.py
  modified:
    - src/sagasmith/vault/__init__.py
    - src/sagasmith/persistence/repositories.py
    - src/sagasmith/tui/commands/control.py
    - src/sagasmith/cli/main.py
    - src/sagasmith/cli/play_cmd.py
    - src/sagasmith/tui/runtime.py
    - src/sagasmith/tui/app.py
    - src/sagasmith/tui/state.py
    - src/sagasmith/tui/widgets/status_panel.py
    - tests/tui/test_control_commands.py

key-decisions:
  - "Player-vault sync rebuilds the player projection from scratch each run so stale spoiler files are removed rather than left behind."
  - "`/recap` reads existing graph rolling_summary and SQLite transcript rows directly, avoiding any LLM call or new cost surface."
  - "Vault repair CLI commands reuse VaultService and rebuild existing FTS5/NetworkX derived layers rather than introducing a separate repair service."

patterns-established:
  - "Player-visible projections are generated artifacts; master vault remains source of truth."
  - "TUI resume derives the next session number from completed turn_records session IDs."

requirements-completed: [CLI-04, VAULT-03, VAULT-04, VAULT-05, VAULT-09, VAULT-10, TUI-08, PERS-05]

duration: 8min
completed: 2026-04-29
---

# Phase 7 Plan 05: Player Vault Sync, Recap, Repair CLI, and Resume Summary

**Spoiler-safe player-vault projection, recap, repair commands, session resume numbering, and persistent sync-warning display are wired into the CLI/TUI path.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-29T08:38:21Z
- **Completed:** 2026-04-29T08:46:02Z
- **Tasks:** 3 completed
- **Files modified:** 14

## Accomplishments

- Implemented player-vault sync that skips `gm_only`, stubs `foreshadowed`, strips `gm_*`/`secrets` frontmatter and `<!-- gm: ... -->` body blocks, removes stale player markdown, and regenerates `index.md`/`log.md`.
- Replaced `/recap` stub with graph-state rolling summary plus recent SQLite transcript rows.
- Added `ttrpg vault rebuild` and `ttrpg vault sync`, plus session-number resume logic and status-panel sync warning rendering.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Player vault sync tests** - `5d58156` (test)
2. **Task 1 GREEN: Player vault sync implementation** - `aef152c` (feat)
3. **Task 2 RED: Recap command test** - `5c71178` (test)
4. **Task 2 GREEN: Recap command implementation** - `4ac8c99` (feat)
5. **Task 3: Vault CLI and resume warning integration** - `74c2a43` (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `src/sagasmith/vault/__init__.py` - Adds `VaultSyncError`, full player-vault projection, generated index/log, projection cleanup, and derived index rebuild helper.
- `src/sagasmith/persistence/repositories.py` - Adds chronological recent transcript retrieval for `/recap`.
- `src/sagasmith/tui/commands/control.py` - Implements `/recap` using rolling summary and recent transcript entries.
- `src/sagasmith/cli/vault_cmd.py` - Adds Typer `vault rebuild` and `vault sync` subcommands.
- `src/sagasmith/cli/main.py` - Registers the `vault` command group.
- `src/sagasmith/cli/play_cmd.py` - Updates headless resume status to report next session number.
- `src/sagasmith/tui/runtime.py` - Computes next session ID/number from completed turn records and seeds runtime accordingly.
- `src/sagasmith/tui/app.py` - Includes session number in play state and refreshes latest sync warning after turns.
- `src/sagasmith/tui/state.py` - Adds vault-sync warning fields to UI status state.
- `src/sagasmith/tui/widgets/status_panel.py` - Renders non-dismissable vault sync warning text.
- `tests/vault/test_sync.py` - Covers projection filtering, stripping, stale cleanup, and sync error wrapping.
- `tests/tui/test_control_commands.py` - Adds `/recap` behavior coverage.
- `tests/cli/test_vault_cmd.py` - Covers vault CLI sync and rebuild success paths.
- `tests/tui/test_resume_and_vault_warning.py` - Covers resumed session numbering and status warning rendering.

## Decisions Made

- Player-vault sync now clears existing player markdown before projection so stale spoiler files do not remain visible after visibility changes.
- Foreshadowed projections intentionally use minimal `BaseVaultFrontmatter` content plus the specified unknown stub body; full page schema fields remain master-only until known.
- Recap is deterministic and provider-free: it only reads graph state and SQLite transcript rows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Removed stale player-vault markdown during sync**
- **Found during:** Task 1 (player-vault sync)
- **Issue:** A sync that only writes current visible pages could leave previously projected files visible after a page becomes `gm_only` or is removed, leaking stale spoiler content.
- **Fix:** `VaultService.sync()` clears existing player-vault markdown before writing the regenerated projection and index/log.
- **Files modified:** `src/sagasmith/vault/__init__.py`, `tests/vault/test_sync.py`
- **Verification:** `uv run pytest tests/vault/test_sync.py -x`
- **Committed in:** `aef152c`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The adjustment strengthens spoiler safety and projection correctness without expanding product scope.

## Known Stubs

None - plan-facing stubs for sync, recap, and repair CLI were replaced.

## Threat Flags

None - new trust surfaces match the plan threat model (CLI repair commands and vault projection filtering).

## Issues Encountered

- Full TUI package pyright includes pre-existing errors in `src/sagasmith/tui/commands/recovery.py`; final typecheck was scoped to changed files and completed with 0 errors, 11 warnings from existing dynamic Textual/runtime patterns.

## Verification

- `uv run pytest tests/vault/test_sync.py tests/tui/test_control_commands.py::test_recap_command_renders_summary_and_recent_transcript tests/cli/test_vault_cmd.py tests/tui/test_resume_and_vault_warning.py -x` ✅
- `uv run ruff check <changed files>` ✅
- `uv run pyright <changed files>` ✅ (0 errors, 11 warnings)

## TDD Gate Compliance

- RED commits present: `5d58156`, `5c71178`
- GREEN commits present after RED: `aef152c`, `4ac8c99`
- REFACTOR commits: none needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 07-06 QA: player-vault leakage regression, quit/resume smoke, repair command coverage, and release-gate checks can exercise the implemented sync/recap/CLI/status surfaces.

## Self-Check: PASSED

- Created files exist on disk.
- Task commits exist in git log.
- `07-05-SUMMARY.md` created in the phase directory.

---
*Phase: 07-memory-vault-and-resume*
*Completed: 2026-04-29*
