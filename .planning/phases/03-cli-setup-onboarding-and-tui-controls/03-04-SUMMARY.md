---
phase: 03-cli-setup-onboarding-and-tui-controls
plan: 04
subsystem: tui
tags: [textual, tui, sqlite, safety-events, pydantic, commands, redaction]

# Dependency graph
requires:
  - phase: 03-cli-setup-onboarding-and-tui-controls
    provides: CommandRegistry, SagaSmithApp, HelpCommand, NarrationArea, build_app() (Plan 03-03)
  - phase: 03-cli-setup-onboarding-and-tui-controls
    provides: OnboardingStore, OnboardingTriple, migration 0003 (Plan 03-02)
  - phase: 02-deterministic-trust-services
    provides: CostGovernor, RedactionCanary, TrustServiceError, open_campaign_db
provides:
  - migration 0004_safety_events.sql: safety_events table with FK to campaigns, visibility/kind CHECK constraints (SAFE-06)
  - SafetyEventRecord Pydantic model (schemas/persistence.py)
  - SafetyEventRepository: append/list_for_campaign
  - SafetyEventService: log_pause/log_line/log_fallback/list_recent with RedactionCanary guard (SAFE-06)
  - All 12 slash commands registered in CommandRegistry: save, recap, sheet, inventory, map, clock, budget, pause, line, retcon, settings, help (TUI-06)
  - PauseCommand: persists SafetyEvent(kind='pause') atomically (SAFE-04)
  - LineCommand: persists SafetyEvent(kind='line') with policy_ref, RedactionCanary rejection (SAFE-05, SAFE-06)
  - SettingsCommand: reads OnboardingStore.reload() and renders triple summary (ONBD-05)
  - BudgetCommand: renders BudgetInspection from runtime CostGovernor (COST-05 UI wiring)
  - Stub commands (save/recap/sheet/inventory/map/retcon) each name their owning future phase
  - SagaSmithApp onboarding_store/safety_events/cost_governor slots for runtime services
affects:
  - Phase 4 (graph runtime wires TUIState.status and fills stub commands)
  - Phase 5 (PF2e vertical slice replaces sheet/inventory/map stubs)
  - Phase 6 (AI GM wires retcon + log_fallback for soft_limit_fade/post_gate_rewrite)
  - Phase 7 (Archivist replaces recap stub)
  - Phase 8 (release hardening replaces retcon stub with confirmation flow)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - PEP 562 __getattr__ in services/__init__.py for lazy SafetyEventService import (breaks circular import chain)
    - SafetyEventService uses _default_canary() factory to defer evals.redaction import (avoids evals.__init__ circular load)
    - Frozen dataclass commands with TYPE_CHECKING guard for SagaSmithApp (avoids TUI circular imports)
    - NarrationArea.logged_lines tracking list for test assertions (public, not _private)
    - All 11 new commands registered in build_app() via a single list loop
    - SafetyEventService._log() uses 'with self.conn:' for atomic SQLite transaction (SAFE-06 T-03-25)

key-files:
  created:
    - src/sagasmith/persistence/migrations/0004_safety_events.sql
    - src/sagasmith/services/safety.py
    - src/sagasmith/tui/commands/control.py
    - src/sagasmith/tui/commands/safety.py
    - src/sagasmith/tui/commands/settings.py
    - tests/persistence/test_safety_events_schema.py
    - tests/services/test_safety.py
    - tests/tui/test_control_commands.py
    - tests/tui/test_safety_commands.py
    - tests/tui/test_settings_command.py
  modified:
    - src/sagasmith/schemas/persistence.py (added SafetyEventRecord)
    - src/sagasmith/schemas/__init__.py (added SafetyEventRecord export)
    - src/sagasmith/persistence/repositories.py (added SafetyEventRepository)
    - src/sagasmith/persistence/__init__.py (added SafetyEventRepository export)
    - src/sagasmith/services/__init__.py (PEP 562 lazy SafetyEventService, __all__ comment)
    - src/sagasmith/tui/app.py (onboarding_store/safety_events/cost_governor slots + TYPE_CHECKING imports)
    - src/sagasmith/tui/runtime.py (full build_app with 12 commands + service bindings)
    - src/sagasmith/tui/commands/__init__.py (exports all 14 command classes)
    - src/sagasmith/tui/widgets/narration.py (logged_lines tracking list)
    - tests/tui/test_help_command.py (updated to verify all 12 commands via build_app)
    - tests/persistence/test_migrations.py (v4 migration count update)
    - tests/persistence/test_campaign_settings_schema.py (v4 migration count update)
    - tests/app/test_campaign.py (schema_version == 4 update)

key-decisions:
  - "PEP 562 __getattr__ in services/__init__.py breaks circular import: services.__init__ → safety.py → persistence.__init__ → app.config → evals.__init__ → fixtures.py → schemas.__init__ → schemas.campaign → services.__init__"
  - "SafetyEventService._canary field uses _default_canary() factory (deferred import) instead of direct RedactionCanary import at module level"
  - "NarrationArea.logged_lines is public (no leading _) for test introspection without pyright 'protected attribute' errors"
  - "service_conn is a single long-lived SQLite connection in build_app() — Textual is single-threaded so thread-safety is not a concern; Phase 4 will revisit for concurrent checkpointing"
  - "stub commands name their owning phase explicitly so future executors have a direct find-the-swap-site signal"

patterns-established:
  - "PEP 562 __getattr__ pattern for lazy exports in __init__.py (breaks circular import without removing export)"
  - "Deferred factory (_default_canary) for frozen dataclass fields with circular import risk"
  - "logged_lines public attribute on NarrationArea for test-safe content introspection"

requirements-completed:
  - TUI-06
  - SAFE-04
  - SAFE-05
  - SAFE-06

# Metrics
duration: 21min
completed: 2026-04-27
---

# Phase 3 Plan 04: Slash Commands, Safety Events, and Phase 3 Completion Summary

**All 12 MVP slash commands registered in TUI; safety_events SQLite table with RedactionCanary SAFE-06 guard; /pause and /line persist player-visible SafetyEventRecords atomically; /settings reads onboarding triple; /budget renders BudgetInspection — 295 passing tests, 12/12 smoke checks.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-04-27T09:21:55Z
- **Completed:** 2026-04-27T09:43:02Z
- **Tasks:** 2 completed
- **Files modified:** 23

## Accomplishments

- Migration `0004_safety_events.sql` adds `safety_events` table with FK to campaigns, `visibility CHECK ('player_visible')` (SAFE-06 structural guarantee), and `kind` CHECK constraint
- `SafetyEventRecord` Pydantic schema, `SafetyEventRepository`, and `SafetyEventService` with `log_pause`/`log_line`/`log_fallback`/`list_recent` — all writes scan via `RedactionCanary` before INSERT
- All 12 slash commands registered: 8 stubs (save/recap/sheet/inventory/map/clock/budget/retcon) + `/pause` (SAFE-04) + `/line` (SAFE-05) + `/settings` (ONBD-05) + `/help` (existing)
- `/pause` and `/line` persist atomic `SafetyEventRecord` rows; secret-shaped topics rejected with narration message and NO DB write
- `/settings` reads `OnboardingStore.reload()` and renders `PlayerProfile`/`ContentPolicy`/`HouseRules` summary
- `/budget` renders `BudgetInspection` from runtime-bound `CostGovernor` (COST-05 UI wiring)
- Pre-existing migration count tests auto-updated to v4 schema

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0004 + SafetyEventRecord + SafetyEventRepository + SafetyEventService (SAFE-06)** - `4978fab` (feat)
2. **Task 2: Eleven slash commands + runtime registration + SAFE-04/05/06 end-to-end (TUI-06)** - `b2ab6b4` (feat)

**Plan metadata:** (docs commit after SUMMARY)

## Files Created/Modified

- `src/sagasmith/persistence/migrations/0004_safety_events.sql` — safety_events table with FK + CHECK constraints
- `src/sagasmith/services/safety.py` — SafetyEventService with lazy RedactionCanary import
- `src/sagasmith/tui/commands/control.py` — 8 control commands (save/recap/sheet/inventory/map/clock/budget/retcon)
- `src/sagasmith/tui/commands/safety.py` — PauseCommand + LineCommand
- `src/sagasmith/tui/commands/settings.py` — SettingsCommand
- `src/sagasmith/schemas/persistence.py` — SafetyEventRecord added
- `src/sagasmith/schemas/__init__.py` — SafetyEventRecord exported
- `src/sagasmith/persistence/repositories.py` — SafetyEventRepository added
- `src/sagasmith/persistence/__init__.py` — SafetyEventRepository exported
- `src/sagasmith/services/__init__.py` — PEP 562 lazy SafetyEventService
- `src/sagasmith/tui/app.py` — onboarding_store/safety_events/cost_governor slots
- `src/sagasmith/tui/runtime.py` — build_app with 12 commands + service bindings
- `src/sagasmith/tui/commands/__init__.py` — all 14 command classes exported
- `src/sagasmith/tui/widgets/narration.py` — logged_lines tracking list
- `tests/tui/test_help_command.py` — updated with TUI-06 12-command assertion
- `tests/persistence/test_safety_events_schema.py` — 4 SAFE-06 schema tests
- `tests/services/test_safety.py` — 10 SafetyEventService tests
- `tests/tui/test_control_commands.py` — 10 control command tests
- `tests/tui/test_safety_commands.py` — 6 safety command end-to-end tests
- `tests/tui/test_settings_command.py` — 3 settings command tests
- `tests/persistence/test_migrations.py` — v4 migration count update (Rule 1 auto-fix)
- `tests/persistence/test_campaign_settings_schema.py` — v4 count update (Rule 1 auto-fix)
- `tests/app/test_campaign.py` — schema_version == 4 update (Rule 1 auto-fix)

## Decisions Made

- Used PEP 562 `__getattr__` in `services/__init__.py` to lazily load `SafetyEventService` — breaks the circular import chain without removing the export from the package's public surface
- `SafetyEventService._canary` uses `_default_canary()` factory (deferred `evals.redaction` import) rather than a module-level import, breaking the same circular chain at the safety module level
- `NarrationArea.logged_lines` is public (no leading `_`) for pyright compliance — test introspection doesn't require protected access
- `service_conn` is a single long-lived SQLite connection in `build_app()` — Textual is single-threaded; Phase 4 will revisit when concurrent checkpointing is added
- Stub commands (save/recap/sheet/inventory/map/retcon) each name their owning future phase explicitly: Phase 4/5/7/8 — direct swap-site discovery for future executors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing migration count tests hardcoded v3 schema**
- **Found during:** Task 1 (test run after adding migration 0004)
- **Issue:** `tests/persistence/test_migrations.py`, `tests/persistence/test_campaign_settings_schema.py`, `tests/app/test_campaign.py` all expected v3 migration count; adding 0004 bumps to v4
- **Fix:** Updated all hardcoded v3 counts to v4 (`[1, 2, 3, 4]`, `schema_version == 4`)
- **Files modified:** `tests/persistence/test_migrations.py`, `tests/persistence/test_campaign_settings_schema.py`, `tests/app/test_campaign.py`
- **Verification:** `uv run pytest tests/persistence/ tests/app/ -q` → all pass
- **Committed in:** `4978fab` (Task 1 commit)

**2. [Rule 3 - Blocking] Circular import: services.__init__ → safety.py → evals.__init__ → fixtures.py → schemas.__init__ → schemas.campaign → services.__init__**
- **Found during:** Task 1 (pyright + import test)
- **Issue:** Adding `from sagasmith.services.safety import SafetyEventService` to `services/__init__.py` created a circular import because `safety.py` imports from `evals.redaction`, triggering `evals/__init__.py` which loads `evals/fixtures.py` which imports `schemas.__init__` which imports `schemas.campaign` which imports `services.secrets` — re-entering `services/__init__.py` while it's partially initialized
- **Fix:** (a) Used PEP 562 `__getattr__` in `services/__init__.py` to defer the import; (b) Used `_default_canary()` factory in `safety.py` to defer the `evals.redaction` import to first-call time
- **Files modified:** `src/sagasmith/services/__init__.py`, `src/sagasmith/services/safety.py`
- **Verification:** `uv run python -c "from sagasmith.schemas import AttackProfile; from sagasmith.services import SafetyEventService; print('ok')"` → ok
- **Committed in:** `4978fab` (Task 1 commit)

**3. [Rule 1 - Bug] AlwaysHitsCanary test pattern for frozen dataclass**
- **Found during:** Task 1 (test_log_atomic_on_canary_hit)
- **Issue:** Plan suggested `patch.object(service._canary, "scan", ...)` but `RedactionCanary` is a frozen dataclass — `FrozenInstanceError` at `setattr`
- **Fix:** Used `AlwaysHitsCanary(RedactionCanary)` subclass pattern (same approach as `BrokenContentPolicy` in Plan 03-02)
- **Files modified:** `tests/services/test_safety.py`
- **Verification:** `test_log_atomic_on_canary_hit` passes
- **Committed in:** `4978fab` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 - Bug, 1 Rule 3 - Blocking)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep. All plan success criteria met.

## Issues Encountered

None — all tests pass after auto-fixes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 is complete: all 4 plans (03-01 through 03-04) have SUMMARYs
- All TUI-06, SAFE-04, SAFE-05, SAFE-06 requirements verified with tests
- 12/12 slash commands registered; `/help` lists all alphabetically
- Safety events table stable at schema v4; RedactionCanary guard proven by test suite
- Stub commands name their future phase owners — Phase 4, 5, 7, 8 executors have clear swap sites
- `service_conn` long-lived connection pattern noted for Phase 4 review when concurrent checkpointing lands

---
*Phase: 03-cli-setup-onboarding-and-tui-controls*
*Completed: 2026-04-27*

## Self-Check: PASSED

- `src/sagasmith/persistence/migrations/0004_safety_events.sql` — FOUND
- `src/sagasmith/services/safety.py` — FOUND
- `src/sagasmith/tui/commands/control.py` — FOUND
- `src/sagasmith/tui/commands/safety.py` — FOUND
- `src/sagasmith/tui/commands/settings.py` — FOUND
- `tests/persistence/test_safety_events_schema.py` — FOUND
- `tests/services/test_safety.py` — FOUND
- `tests/tui/test_control_commands.py` — FOUND
- `tests/tui/test_safety_commands.py` — FOUND
- `tests/tui/test_settings_command.py` — FOUND
- Task 1 commit `4978fab` — FOUND in git log
- Task 2 commit `b2ab6b4` — FOUND in git log
