---
phase: 06-ai-gm-story-loop
plan: 06
subsystem: narration-recovery
tags: [graph-runtime, langgraph, checkpoints, turn-records, tui, retry, discard, deterministic, regression]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: [GraphRuntime, CheckpointRefRepository, pre_narration checkpoint, interrupt_before orator, SqliteSaver]
  - phase: 06-ai-gm-story-loop
    provides: [Orator scene rendering pipeline (06-04)]
provides:
  - discard_incomplete_turn() on GraphRuntime for discarding incomplete narration
  - retry_narration() on GraphRuntime for re-running Orator + Archivist from checkpoint
  - _rewind_to_checkpoint() LangGraph checkpoint fork helper
  - TurnRecord narrated/discarded/retried status values
  - /retry and /discard TUI commands
  - Deterministic stability regression test suite
affects: [phase-6-ai-gm-story-loop, graph-runtime, persistence, tui, turn-lifecycle]

tech-stack:
  added: []
  patterns:
    - LangGraph checkpoint rewind via update_state with checkpoint_id + checkpoint_ns
    - TurnRecord status state machine: needs_vault_repair → narrated/retried/discarded → complete
    - TUI recovery commands gated on snapshot.next == ("orator",)

key-files:
  created:
    - src/sagasmith/persistence/migrations/0006_turn_record_status.sql
    - src/sagasmith/tui/commands/recovery.py
    - tests/integration/test_narration_recovery.py
  modified:
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/schemas/persistence.py
    - src/sagasmith/tui/commands/__init__.py
    - src/sagasmith/tui/runtime.py
    - tests/app/test_campaign.py
    - tests/persistence/test_campaign_settings_schema.py
    - tests/persistence/test_migrations.py

key-decisions:
  - "LangGraph checkpoint rewind uses update_state with checkpoint_id + checkpoint_ns=\"\" (required by SqliteSaver.put_writes)."
  - "TurnRecord status values narrated/discarded/retried added alongside existing complete/needs_vault_repair — state machine documented in TurnRecord docstring."
  - "Migration 0006 disables FK enforcement during table swap to avoid agent_skill_log FK constraint conflict with DROP TABLE."
  - "/retry and /discard TUI commands gated on snapshot.next == ('orator',) and matching turn_id — disabled when no incomplete narration exists."

patterns-established:
  - "GraphRuntime._rewind_to_checkpoint() forks thread from a specific checkpoint via LangGraph update_state"
  - "Recovery commands check graph snapshot state before invoking runtime methods"

requirements-completed: [GRAPH-06, GRAPH-07, D-13, D-14]

duration: 20min
completed: 2026-04-28
---

# Phase 6 Plan 06: Narration Discard + Recovery Commands Summary

**LangGraph checkpoint-based narration recovery with discard/retry flows, TurnRecord status transitions, /retry and /discard TUI commands, and deterministic stability regression tests.**

## Performance

- **Duration:** 20 min
- **Tasks:** 5 implementation steps
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- Added `discard_incomplete_turn()` and `retry_narration()` to GraphRuntime, enabling the player to recover from incomplete narration by rewinding to the pre-narration checkpoint.
- Implemented `_rewind_to_checkpoint()` helper using LangGraph's `update_state` with `checkpoint_id` + `checkpoint_ns` to fork a thread from a specific checkpoint snapshot.
- Extended `TurnRecord.status` Literal with `narrated`, `discarded`, and `retried` values; updated the DB CHECK constraint via migration 0006 (FK-safe table swap).
- Created `/retry` and `/discard` TUI commands gated on `snapshot.next == ("orator",)` and matching turn_id.
- Wrote 11 regression tests covering: discard flow (4), retry flow (3), deterministic stability (4) including byte-identical `check_results` assertion across happy vs. retry paths and orphan-free discarded turns.

## Task Commits

1. **Runtime + schema + migration** - `6f13e15` (feat)
2. **Regression tests** - `53c3ea8` (test)
3. **TUI recovery commands** - `ba1b349` (feat)
4. **Schema version test fixes** - `887b339`, `d93bd48` (fix)

## Files Created/Modified

- `src/sagasmith/graph/runtime.py` — Added `discard_incomplete_turn()`, `retry_narration()`, `_rewind_to_checkpoint()` methods.
- `src/sagasmith/schemas/persistence.py` — Extended `TurnRecord.status` Literal with `narrated`, `discarded`, `retried`; documented state machine.
- `src/sagasmith/persistence/migrations/0006_turn_record_status.sql` — Expands DB CHECK constraint for new status values (FK-safe table swap).
- `src/sagasmith/tui/commands/recovery.py` — `/retry` and `/discard` TUI commands with incomplete-narration gating.
- `src/sagasmith/tui/commands/__init__.py` — Exports `RetryCommand` and `DiscardCommand`.
- `src/sagasmith/tui/runtime.py` — Registers `/retry` and `/discard` in the command registry.
- `tests/integration/test_narration_recovery.py` — 11 regression tests for discard, retry, and deterministic stability.
- `tests/app/test_campaign.py` — Updated expected schema version to 6.
- `tests/persistence/test_campaign_settings_schema.py` — Updated expected migration list.
- `tests/persistence/test_migrations.py` — Updated expected migration list and schema version.

## Decisions Made

- LangGraph checkpoint rewind requires `checkpoint_ns=""` in the config alongside `checkpoint_id` — without it, `SqliteSaver.put_writes` raises `KeyError: 'checkpoint_ns'`.
- Migration 0006 disables FK enforcement (`PRAGMA foreign_keys = OFF`) during the `turn_records` table swap because `agent_skill_log` has a `FOREIGN KEY (turn_id) REFERENCES turn_records(turn_id)`.
- TUI recovery commands check `snapshot.next == ("orator",)` and `turn_id` match to determine if incomplete narration exists, avoiding false positives from stale state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added checkpoint_ns to LangGraph rewind config**
- **Found during:** Step 4 (regression tests)
- **Issue:** `graph.update_state` with `checkpoint_id` but without `checkpoint_ns` caused `KeyError: 'checkpoint_ns'` in `SqliteSaver.put_writes`.
- **Fix:** Added `checkpoint_ns: ""` to the rewind config dict in `_rewind_to_checkpoint()`.
- **Files modified:** `src/sagasmith/graph/runtime.py`
- **Verification:** All 11 narration recovery tests pass.
- **Committed in:** `6f13e15`

**2. [Rule 3 - Blocking] Migration 0006 FK-safe table swap**
- **Found during:** Step 4 (regression tests)
- **Issue:** `DROP TABLE turn_records` with `PRAGMA foreign_keys = ON` breaks `agent_skill_log`'s FK reference, causing `cursor.lastrowid is None` on subsequent inserts.
- **Fix:** Added `PRAGMA foreign_keys = OFF` / `PRAGMA foreign_key_check` / `PRAGMA foreign_keys = ON` around the table swap in migration 0006.
- **Files modified:** `src/sagasmith/persistence/migrations/0006_turn_record_status.sql`
- **Verification:** All 664 tests pass (1 skipped).
- **Committed in:** `53c3ea8`

**3. [Rule 1 - Bug] Updated schema version assertions in existing tests**
- **Found during:** Full test suite run
- **Issue:** Three existing tests hardcoded schema version == 5; migration 0006 bumped it to 6.
- **Fix:** Updated assertions in `test_campaign.py`, `test_campaign_settings_schema.py`, and `test_migrations.py`.
- **Files modified:** `tests/app/test_campaign.py`, `tests/persistence/test_campaign_settings_schema.py`, `tests/persistence/test_migrations.py`
- **Verification:** All 664 tests pass.
- **Committed in:** `887b339`, `d93bd48`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** The `checkpoint_ns` fix was required for LangGraph API compatibility. The FK-safe migration was required to avoid breaking existing FK constraints. The schema version test updates were a direct consequence of adding migration 0006.

## Known Stubs

None — all plan deliverables are fully implemented.

## Threat Flags

None — no new security surface. Recovery commands operate on existing graph state and persistence layer.

## Issues Encountered

- LangGraph's `update_state` with `checkpoint_id` requires `checkpoint_ns` in the config — undocumented in the LangGraph API but required by `SqliteSaver.put_writes`.
- SQLite table recreation with `DROP TABLE` + `ALTER TABLE RENAME` can break FK references when `PRAGMA foreign_keys = ON` — solved by temporarily disabling FK enforcement during the migration.

## User Setup Required

None — no external service configuration required.

## Verification

- `uv run ruff check` on all new/modified files — passed.
- `uv run pytest tests/integration/test_narration_recovery.py` — 11 passed.
- `uv run pytest tests/graph/test_checkpoints.py tests/integration/test_tui_graph_smoke.py` — 15 passed.
- `uv run pytest` — 664 passed, 1 skipped.

## Next Phase Readiness

- Narration recovery is complete: players can `/retry` or `/discard` incomplete narration without affecting deterministic state.
- `TurnRecord` status transitions (`narrated`, `discarded`, `retried`) enable Phase 7/8 vault and repair flows to distinguish turn outcomes.
- Plan 06-08 (integration testing) can now test the full narration recovery cycle end-to-end.

## Self-Check: PENDING

- Created files verified on disk.
- Task commits verified in git history.
- Summary file verified on disk.

---

*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
