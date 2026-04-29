---
phase: 08-retcon-repair-and-release-hardening
plan: 01
subsystem: persistence
tags: [sqlite, retcon, audit, canonical-reads, vault]

requires:
  - phase: 07-memory-vault-and-resume
    provides: turn-close vault writes, transcript context, vault repair/sync surfaces
provides:
  - SQLite schema version 8 for retained retcon audit metadata and vault-write impact rows
  - Typed RetconAuditRecord and VaultWriteAuditRecord persistence contracts
  - Centralized canonical turn/transcript repository helpers excluding retconned rows by default
  - Turn-close vault-write audit recording after successful master vault writes
affects: [phase-8-retcon-service, recap, memory-packets, vault-rebuild, release-hardening]

tech-stack:
  added: []
  patterns:
    - audit-retained retcon status using SQLite CHECK constraints and typed repositories
    - canonical reads routed through shared repository helpers instead of scattered status filters

key-files:
  created:
    - src/sagasmith/persistence/migrations/0008_retcon_audit.sql
    - tests/persistence/test_retcon_repositories.py
  modified:
    - src/sagasmith/schemas/persistence.py
    - src/sagasmith/schemas/export.py
    - src/sagasmith/persistence/repositories.py
    - src/sagasmith/persistence/turn_close.py
    - src/sagasmith/agents/archivist/transcript_context.py
    - tests/persistence/test_migrations.py
    - tests/persistence/test_campaign_settings_schema.py
    - tests/persistence/test_turn_close_vault.py
    - tests/agents/archivist/test_transcript_context.py

key-decisions:
  - "Retconned turn rows are retained and marked with status='retconned'; canonical helpers exclude them by default while debug/audit methods can opt in."
  - "Vault-write audit rows are recorded only after successful master-vault writes, preserving exact retcon impact metadata without false positives."

patterns-established:
  - "Canonical transcript access goes through TranscriptRepository.list_canonical_for_campaign(..., include_retconned=False)."
  - "Retcon eligibility goes through TurnRecordRepository.list_recent_completed and list_affected_suffix."

requirements-completed: [QA-01, QA-02]

duration: 5 min
completed: 2026-04-29
---

# Phase 8 Plan 01: Retcon Audit Persistence Summary

**Audit-retained retcon persistence with canonical-only turn/transcript reads and vault-write impact tracking.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-29T16:59:10Z
- **Completed:** 2026-04-29T17:04:21Z
- **Tasks:** 3 completed
- **Files modified:** 10

## Accomplishments

- Added migration `0008_retcon_audit.sql` with `retconned` turn status, `retcon_audit`, and `vault_write_audit` tables while preserving raw turn rows and `sync_warning`.
- Added typed retcon/vault-write schemas and repositories for recent completed turns, affected suffixes, retcon marking, retcon audit records, and vault-write audit records.
- Updated Archivist transcript context to use canonical transcript reads so retconned transcript rows are excluded from memory context by default.
- Recorded durable vault-write audit rows during turn close only after successful master vault writes.

## Task Commits

1. **Task 1 RED: Add retcon and vault-write audit schema tests** - `def00a4` (test)
2. **Task 1 GREEN: Add retcon and vault-write audit schema** - `afaa6a1` (feat)
3. **Task 2 RED: Canonical query and eligibility repository tests** - `4d84c4f` (test)
4. **Task 2 GREEN: Canonical query and eligibility repositories** - `84acd95` (feat)
5. **Task 3 RED: Vault-write audit tracking tests** - `9379bde` (test)
6. **Task 3 GREEN: Vault writes recorded during turn close** - `2a12759` (feat)
7. **Schema export fix** - `faf411b` (fix)

**Plan metadata:** committed separately after this summary.

## Files Created/Modified

- `src/sagasmith/persistence/migrations/0008_retcon_audit.sql` - Schema version 8 for retconned turn status, retcon audits, and vault-write audits.
- `src/sagasmith/schemas/persistence.py` - Added `retconned` status and typed audit models.
- `src/sagasmith/schemas/export.py` - Exports new persisted audit schemas.
- `src/sagasmith/persistence/repositories.py` - Added canonical transcript helper, retcon eligibility/marking, retcon audit repository, and vault-write audit repository.
- `src/sagasmith/agents/archivist/transcript_context.py` - Uses canonical transcript helper by default.
- `src/sagasmith/persistence/turn_close.py` - Appends vault-write audit rows after successful vault page writes.
- `tests/persistence/test_retcon_repositories.py` - Covers retcon schema, canonical query behavior, and audit repositories.
- `tests/persistence/test_turn_close_vault.py` - Covers vault-write audit success/failure behavior.
- `tests/persistence/test_migrations.py` and `tests/persistence/test_campaign_settings_schema.py` - Updated migration/schema expectations.
- `tests/agents/archivist/test_transcript_context.py` - Covers default exclusion of retconned transcript context.

## Decisions Made

- Retcon retention uses a first-class `retconned` status rather than deleting rows or adding destructive-delete metadata.
- Canonical transcript/memory consumers should use repository-level canonical helpers; explicit audit/debug access must opt in with `include_retconned=True` or turn-specific methods.
- Vault-write audit rows reflect successful filesystem side effects and are not inserted before `write_page()` succeeds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Exported new persisted audit schemas**
- **Found during:** Final verification after Task 3
- **Issue:** The plan added persisted Pydantic models, but schema export still omitted them, leaving persisted boundary schema exports incomplete.
- **Fix:** Added `RetconAuditRecord` and `VaultWriteAuditRecord` to `LLM_BOUNDARY_AND_PERSISTED_MODELS` and updated schema export regression count.
- **Files modified:** `src/sagasmith/schemas/export.py`, `tests/persistence/test_migrations.py`
- **Verification:** Targeted pytest suite and ruff check passed.
- **Committed in:** `faf411b`

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality).
**Impact on plan:** The deviation completes the intended typed persistence contract without changing architecture or scope.

## Known Stubs

None.

## Threat Flags

None beyond the planned retcon/canonical-read trust surfaces in the plan threat model.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/persistence/test_migrations.py tests/persistence/test_campaign_settings_schema.py tests/persistence/test_retcon_repositories.py tests/agents/archivist/test_transcript_context.py tests/persistence/test_turn_close_vault.py -x` — 28 passed.
- `uv run ruff check src/sagasmith/persistence src/sagasmith/agents/archivist tests/persistence tests/agents/archivist` — passed.

## Next Phase Readiness

- Ready for 08-02 RetconService work to consume affected suffixes, retcon audit append, checkpoint refs, canonical transcript helpers, and vault-write impact rows.
- No blockers.

## Self-Check: PASSED

- Created migration exists: `src/sagasmith/persistence/migrations/0008_retcon_audit.sql`.
- Created test file exists: `tests/persistence/test_retcon_repositories.py`.
- Task commits found: `def00a4`, `afaa6a1`, `4d84c4f`, `84acd95`, `9379bde`, `2a12759`, `faf411b`.

---
*Phase: 08-retcon-repair-and-release-hardening*
*Completed: 2026-04-29*
