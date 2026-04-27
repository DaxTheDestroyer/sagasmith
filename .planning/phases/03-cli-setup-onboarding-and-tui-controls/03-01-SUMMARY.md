---
phase: 03-cli-setup-onboarding-and-tui-controls
plan: 01
subsystem: cli
tags: [typer, sqlite, pydantic, campaign, cli, migrations, secrets]

# Dependency graph
requires:
  - phase: 02-deterministic-trust-services
    provides: SecretRef, RedactionCanary, TrustServiceError, open_campaign_db, apply_migrations
provides:
  - CampaignManifest Pydantic model + TOML serialization
  - ProviderSettings Pydantic model stored in SQLite settings table
  - CampaignPaths value object + resolve_campaign_paths/validate_campaign_paths
  - SettingsRepository (RedactionCanary-guarded SQLite upsert/get)
  - SQLite schema v2 with campaigns + settings tables (FK enforced)
  - sagasmith init command (CLI-01, CLI-02)
  - sagasmith play command (CLI-03, status line + exit codes)
  - sagasmith configure command (SecretRef merge, no secret echo)
  - sagasmith demo command (CLI-05, delegates to smoke harness)
  - Smoke check #12: cli.init.creates_storage
affects:
  - 03-02-PLAN.md (onboarding inserts via SettingsRepository/open_campaign)
  - 03-03-PLAN.md (TUI resolves campaign via resolve_campaign_paths/validate_campaign_paths)
  - 03-04-PLAN.md (slash commands open campaigns, configure settings)

# Tech tracking
tech-stack:
  added:
    - tomllib (stdlib, Python 3.12 read)
    - hand-rolled TOML writer (avoids tomli_w dep for six scalar fields)
    - secrets.token_hex (collision-resistant campaign IDs, no new dep)
  patterns:
    - Annotated[Type, typer.Option(...)] pattern for all CLI args (avoids B008 ruff rule)
    - SettingsRepository: frozen dataclass + RedactionCanary guard on every put
    - init_campaign: deterministic mkdir-first idempotency guard
    - open_campaign: validate_campaign_paths + model_validate for typed errors at CLI boundary
    - Append-only smoke check convention (harness.py grows monotonically)

key-files:
  created:
    - src/sagasmith/persistence/migrations/0002_campaign_and_settings.sql
    - src/sagasmith/schemas/campaign.py
    - src/sagasmith/app/paths.py
    - src/sagasmith/app/config.py
    - src/sagasmith/app/campaign.py
    - src/sagasmith/cli/init_cmd.py
    - src/sagasmith/cli/play_cmd.py
    - src/sagasmith/cli/configure_cmd.py
    - tests/app/__init__.py
    - tests/app/test_paths.py
    - tests/app/test_config.py
    - tests/app/test_campaign.py
    - tests/cli/__init__.py
    - tests/cli/test_init_cmd.py
    - tests/cli/test_play_cmd.py
    - tests/cli/test_configure_cmd.py
    - tests/persistence/test_campaign_settings_schema.py
  modified:
    - src/sagasmith/schemas/__init__.py (added CampaignManifest, ProviderSettings exports)
    - src/sagasmith/schemas/export.py (added CampaignManifest, ProviderSettings to boundary list)
    - src/sagasmith/app/__init__.py (added SettingsRepository re-export)
    - src/sagasmith/persistence/__init__.py (added SettingsRepository re-export)
    - src/sagasmith/cli/main.py (registered init/play/configure/demo commands)
    - src/sagasmith/evals/harness.py (added smoke check #12)
    - tests/evals/test_smoke_cli.py (updated for 12/12 and cli.init.creates_storage)
    - tests/persistence/test_migrations.py (updated for v2 schema: 2 migrations, new tables)
    - tests/schemas/test_json_schema_export.py (updated EXPECTED_SCHEMA_NAMES for 27 models)
    - tests/providers/test_models.py (updated schema count to 27)

key-decisions:
  - "CampaignManifest uses hand-rolled TOML writer (not tomli_w dep) for six scalar fields"
  - "SettingsRepository uses RedactionCanary guard on every put — mirrors turn_close.py invariant"
  - "Smoke check count bumped to 12 (plan said 11 but persistence.turn_close was already check #11)"
  - "Pre-existing tests updated for schema v2 (2 migrations, 27 exported models) as Rule 1 auto-fixes"
  - "play_cmd keeps session_id=1 with TODO comment referencing Phase 7 for session management"

patterns-established:
  - "Annotated[Type, typer.Option(...)] for all CLI args to satisfy ruff B008"
  - "init_campaign uses mkdir(exist_ok=False) as idempotency guard before any DB write"
  - "SettingsRepository.put always runs RedactionCanary scan before INSERT/UPDATE"

requirements-completed:
  - CLI-01
  - CLI-02
  - CLI-03
  - CLI-05

# Metrics
duration: 16min
completed: 2026-04-27
---

# Phase 3 Plan 01: Campaign Lifecycle, CLI Shell, and v2 Schema Summary

**SQLite schema v2 with campaigns/settings tables, CampaignManifest/ProviderSettings/CampaignPaths contracts, SettingsRepository with RedactionCanary guard, and four Typer commands (init/play/configure/demo) with 190 passing tests and 12/12 smoke checks.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-04-27T14:24:26Z
- **Completed:** 2026-04-27T14:40:12Z
- **Tasks:** 2 completed
- **Files modified:** 27

## Accomplishments

- SQLite schema extended to v2 with `campaigns` and `settings` tables (foreign key enforcement)
- `CampaignManifest`, `ProviderSettings`, `CampaignPaths`, `SettingsRepository` added and exported
- Four Typer CLI commands registered: `init`, `play`, `configure`, `demo`
- `SettingsRepository.put` guards all writes with `RedactionCanary` (mirrors turn_close.py invariant)
- `init_campaign` uses hand-rolled TOML writer avoiding `tomli_w` dependency
- Smoke suite grows to 12/12 with new `cli.init.creates_storage` check
- 190 unit + smoke tests all green; ruff and pyright clean on all touched files

## Task Commits

Each task was committed atomically:

1. **Task 1: Schema migration v2 + CampaignManifest/ProviderSettings models + app.paths** - `3927e3e` (feat)
2. **Task 2: Campaign lifecycle domain + init/play/configure/demo CLI commands + smoke check #12** - `2ffdbdc` (feat)

## Files Created/Modified

- `src/sagasmith/persistence/migrations/0002_campaign_and_settings.sql` — campaigns + settings tables with FK
- `src/sagasmith/schemas/campaign.py` — CampaignManifest, ProviderSettings Pydantic models + generate_campaign_id
- `src/sagasmith/app/paths.py` — CampaignPaths frozen dataclass + resolve/validate helpers
- `src/sagasmith/app/config.py` — SettingsRepository with RedactionCanary-guarded put
- `src/sagasmith/app/campaign.py` — init_campaign, open_campaign, slugify lifecycle functions
- `src/sagasmith/cli/init_cmd.py` — sagasmith init command (CLI-01, CLI-02)
- `src/sagasmith/cli/play_cmd.py` — sagasmith play command (CLI-03, status line)
- `src/sagasmith/cli/configure_cmd.py` — sagasmith configure command (SecretRef merge)
- `src/sagasmith/cli/main.py` — updated to register init/play/configure/demo + demo inline
- `src/sagasmith/evals/harness.py` — appended smoke check #12 (cli.init.creates_storage)
- `tests/app/test_paths.py`, `test_config.py`, `test_campaign.py` — app subpackage tests
- `tests/cli/test_init_cmd.py`, `test_play_cmd.py`, `test_configure_cmd.py` — CLI tests
- `tests/persistence/test_campaign_settings_schema.py` — migration v2 schema tests

## Decisions Made

- Used hand-rolled TOML writer rather than adding `tomli_w` dependency — six scalar fields don't justify a new dep (plan specified "the agent's Discretion")
- `SettingsRepository` is a frozen dataclass imported into both `app/__init__.py` and `persistence/__init__.py` for CLI convenience; the domain module lives in `app/config.py`
- Smoke check count is 12 (not 11 as the plan said): `persistence.turn_close.transaction_ordering` was already check #11 from Phase 2; `cli.init.creates_storage` is check #12
- Pre-existing tests hardcoding v1 migration count and 25-model export count required updates (Rule 1 auto-fixes) when the new migration and models were added

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing tests had hardcoded migration count and schema export count**
- **Found during:** Task 2 (full test suite run)
- **Issue:** `tests/persistence/test_migrations.py` expected `[1]` from `apply_migrations` and `schema_version == 1`; `tests/schemas/test_json_schema_export.py` expected 25 models; `tests/providers/test_models.py` expected 25 models — all now incorrect after adding migration v2 and 2 new models
- **Fix:** Updated all hardcoded values to reflect v2 schema (2 migrations → `[1, 2]`, 27 models, added new table names to assertions)
- **Files modified:** `tests/persistence/test_migrations.py`, `tests/schemas/test_json_schema_export.py`, `tests/providers/test_models.py`
- **Verification:** `uv run pytest -q` → 190 passed, 1 skipped
- **Committed in:** `2ffdbdc` (Task 2 commit)

**2. [Rule 1 - Bug] Smoke check #11 count mismatch**
- **Found during:** Task 2 (test run of test_smoke_cli.py)
- **Issue:** Plan said to add "check #11" and assert "11/11 checks", but Phase 2 had already added check #11 (`persistence.turn_close.transaction_ordering`); our addition is actually check #12
- **Fix:** Updated `test_smoke_fast_mode_exits_zero` to assert `12/12` and added `cli.init.creates_storage` to the check names list
- **Files modified:** `tests/evals/test_smoke_cli.py`
- **Verification:** `uv run sagasmith smoke --mode fast` → 12/12 checks passed
- **Committed in:** `2ffdbdc` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep. All plan success criteria met.

## Issues Encountered

None — all tests pass, all CLI commands work as specified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Campaign lifecycle (init/play/configure/demo) complete and tested
- `open_campaign` and `SettingsRepository` ready for Plan 03-02 (onboarding)
- `resolve_campaign_paths` and `validate_campaign_paths` ready for Plan 03-03 (TUI)
- All secret hygiene invariants verified (configure never echoes, repository rejects payloads)
- Schema v2 stable and deployed; no further migration changes planned for Phase 3

---
*Phase: 03-cli-setup-onboarding-and-tui-controls*
*Completed: 2026-04-27*

## Self-Check: PASSED
