---
phase: 03-cli-setup-onboarding-and-tui-controls
verified: 2026-04-27T16:02:31Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `sagasmith init --name 'Test' --path ./tmp-verify --provider fake` then `sagasmith play --campaign ./tmp-verify` to confirm the Textual TUI launches with four visible regions (narration, status panel, safety bar, input line)"
    expected: "TUI renders four regions; typing /help lists 12 commands alphabetically; typing /pause shows [SAFETY] Paused.; Ctrl+Q exits cleanly and closes the SQLite WAL"
    why_human: "Textual TUI requires a terminal; run_test() confirms mount but not the full interactive rendering experience or WAL checkpoint-on-exit behavior"
  - test: "In the launched TUI, type `/line graphic violence` then Ctrl+Q; open the campaign.sqlite with sqlite3 and run `SELECT kind, policy_ref, action_taken FROM safety_events;`"
    expected: "One row: kind=line, policy_ref='graphic violence', action_taken='redlined:graphic violence', visibility='player_visible'"
    why_human: "Confirms the end-to-end flow from TUI input through SafetyEventService to SQLite, with no secrets in the record"
---

# Phase 3: CLI Setup, Onboarding, and TUI Controls Verification Report

**Phase Goal:** User can initialize a local campaign, complete onboarding, and use responsive control commands in the Textual shell
**Verified:** 2026-04-27T16:02:31Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run first-time setup, choose or confirm campaign name/path, create local campaign storage, and start or resume without a hosted server | ✓ VERIFIED | `sagasmith init` creates `campaign.sqlite`, `player_vault/`, `campaign.toml`; `sagasmith play --campaign <path>` launches Textual TUI; all artifacts exist and are wired; 295 tests green including `test_init_creates_all_artifacts_with_args`, `test_play_on_fresh_campaign_prints_status_line` |
| 2 | User can complete onboarding for story preferences, content policy, house rules, budget, dice UX, campaign length, and character mode, then review/edit before commit | ✓ VERIFIED | `OnboardingWizard` (9-phase state machine) + `OnboardingStore` exist, are substantive (18 KB + 6 KB), and are tested; `parse_answer` covers all 8 `PromptFieldKind` branches; `edit()` + `review()` + `commit()` chain verified by `test_wizard_happy_path_reaches_done`, `test_wizard_edit_valid_field_updates_draft`, `test_commit_writes_all_three_rows` |
| 3 | User sees a Textual interface with narration area, status panel, safety bar, input line, scrollback, and supported slash-command help | ✓ VERIFIED | `SagaSmithApp` composes `NarrationArea`, `StatusPanel`, `SafetyBar`, `InputLine`; `_load_scrollback()` reads up to 50 transcript entries from SQLite; `HelpCommand` lists all registered commands; verified by `test_app_mounts_with_four_regions`, `test_scrollback_loads_on_mount`, `test_slash_help_dispatches_and_appends_help` |
| 4 | User can type natural-language actions and use all 12 slash-command entries (`/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/clock`, `/budget`, `/pause`, `/line`, `/retcon`, `/settings`, `/help`) | ✓ VERIFIED | All 12 commands registered in `build_app()` via `CommandRegistry`; `test_help_lists_registered_commands` confirms all 12 in alphabetical order; per-command tests in `test_control_commands.py`, `test_safety_commands.py`, `test_settings_command.py` confirm narration output for each |
| 5 | User can invoke `/pause` or `/line` during play setup/control states and see a persisted, player-visible safety event without exposing secrets or GM-only spoilers | ✓ VERIFIED | `PauseCommand` calls `SafetyEventService.log_pause()` → atomic SQLite INSERT; `LineCommand` calls `SafetyEventService.log_line()` with RedactionCanary guard; `safety_events` table has `visibility CHECK ('player_visible')` constraint; verified by `test_pause_persists_safety_event`, `test_line_persists_safety_event_with_topic`, `test_line_rejects_secret_shaped_topic`, `test_safety_events_check_visibility_rejects_gm_only` |

**Score:** 5/5 truths verified

---

## Plan-by-Plan Criteria

### Plan 03-01: Campaign Lifecycle + CLI Shell

| Criterion | Status | Evidence |
|-----------|--------|----------|
| CLI-01: `sagasmith init` creates `campaign.sqlite`, `player_vault/`, and `campaign.toml` | ✓ PASS | `src/sagasmith/cli/init_cmd.py` calls `init_campaign()`; `test_init_creates_all_artifacts_with_args` verifies all three artifacts; smoke check #12 `cli.init.creates_storage` passes |
| CLI-02: User supplies campaign name and path interactively (TTY) or via flags (non-TTY) | ✓ PASS | `init_cmd.py` uses `sys.stdin.isatty()` check; non-TTY defaults to `./<slug>/`; `test_init_requires_name_in_non_interactive_mode` verifies exit 2 when no `--name` in non-TTY |
| CLI-03: `sagasmith play --campaign <path>` opens existing campaign without a hosted server | ✓ PASS | `play_cmd.py` now calls `build_app(campaign)` and `app.run()`; `--headless-status` flag preserves test contract; `test_play_on_fresh_campaign_prints_status_line` green |
| CLI-05: `sagasmith demo --campaign <path>` runs smoke via `DeterministicFakeClient`; no paid calls | ✓ PASS | `demo` command calls `run_smoke()`; smoke suite runs 12/12 checks with no network; verified by `uv run sagasmith smoke --mode fast` → `12/12 checks passed` |
| Settings persistence: `ProviderSettings` round-trips through `SettingsRepository` | ✓ PASS | `test_put_provider_settings_round_trips` and `test_init_persists_provider_settings` both green |
| Secret hygiene: configure never echoes secrets; `SettingsRepository.put` rejects secret-shaped payloads | ✓ PASS | `test_configure_never_echoes_secret` and `test_put_rejects_raw_secret_payload` both green |
| Schema migration: DB schema v2 with `campaigns` and `settings` tables, FK enforcement | ✓ PASS | Migration `0002_campaign_and_settings.sql` applies; `test_migration_0002_creates_campaigns_and_settings` and `test_settings_foreign_key_enforced` both green |

### Plan 03-02: Onboarding Wizard Domain + SQLite Store

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ONBD-01: 9 phases cover all required fields (genre, tone, touchstones, pillar weights, pacing, combat style, dice UX, campaign length, character mode, death policy, budget) | ✓ PASS | `ONBOARDING_PHASES` has 9 entries; `test_ONBOARDING_PHASES_covers_all_phases` confirms length and order; `test_wizard_happy_path_reaches_done` drives all 9 |
| ONBD-02: `hard_limits`, `soft_limits`, `preferences` captured in CONTENT_POLICY phase | ✓ PASS | `ContentPolicy` schema has all three fields; `SOFT_LIMIT_MAP` parse_answer branch rejects bad enum; `test_parse_answer_soft_limit_map_rejects_bad_enum` green |
| ONBD-03: Review phase exposes draft for inspection; accepts field-path edits before commit | ✓ PASS | `review()`, `edit()`, `build_records()` all implemented in `wizard.py`; `test_wizard_edit_valid_field_updates_draft`, `test_wizard_review_step_without_confirmation_stays_on_review` green |
| ONBD-04: Validated `PlayerProfile`, `ContentPolicy`, `HouseRules` persist atomically | ✓ PASS | `OnboardingStore.commit()` uses `with self.conn:` for three-table atomic INSERT; `test_commit_writes_all_three_rows` and `test_commit_is_atomic_on_validation_failure` green |
| ONBD-05: `commit()` twice overwrites without data loss; re-run supported | ✓ PASS | `INSERT OR REPLACE` semantics; `test_commit_twice_overwrites` green |
| DB invariant: triple always complete or absent; partial state raises `TrustServiceError` | ✓ PASS | `OnboardingStore.reload()` checks all three tables; `test_reload_raises_on_partial_state` green |
| Migration 0003 applies cleanly after 0002; schema reaches v3 | ✓ PASS | Confirmed by `apply_migrations` returning `[1,2,3]`; `test_migration_0002_creates_campaigns_and_settings` updated to v3 count |

### Plan 03-03: Textual TUI Shell + CommandRegistry + /help

| Criterion | Status | Evidence |
|-----------|--------|----------|
| TUI-01: Textual app has four named regions (narration, status, safety, input) on mount | ✓ PASS | `SagaSmithApp.compose()` yields `SafetyBar`, `NarrationArea(id="narration-area")`, `StatusPanel(id="status-panel")`, `InputLine(id="input-line")`; `test_app_mounts_with_four_regions` green |
| TUI-02: Free-form input echoes to narration and clears the input line | ✓ PASS | `on_player_input_submitted()` calls `narration.append_line(f"> {text}")`; `test_freeform_input_echoes_to_narration` green |
| TUI-03: Scrollback loaded from SQLite `transcript_entries` on mount, capped at 50 | ✓ PASS | `_load_scrollback()` in `runtime.py` with `SCROLLBACK_LIMIT = 50`; `test_scrollback_loads_on_mount` inserts 3 rows and verifies they appear |
| TUI-04: Status panel renders HP, conditions, quest, location, clock, last rolls from `StatusSnapshot` | ✓ PASS | `StatusPanel._format_snapshot()` renders all 7 fields; `test_status_snapshot_format_hp_*` and `test_status_snapshot_format_clock_*` green |
| TUI-05: `/help` lists all registered commands automatically | ✓ PASS | `HelpCommand.handle()` iterates `registry.all()`; `test_help_lists_registered_commands` and `test_slash_help_dispatches_and_appends_help` green |
| `sagasmith play` launches Textual TUI; `--headless-status` preserves test contract | ✓ PASS | `play_cmd.py` calls `build_app(campaign).run()`; all Plan 03-01 play tests updated to use `--headless-status` |

### Plan 03-04: Eleven Commands + Safety Events + Phase 3 Completion

| Criterion | Status | Evidence |
|-----------|--------|----------|
| TUI-06: All 12 required slash commands exist, listed by `/help`, produce ≥1 narration response | ✓ PASS | 12 commands registered in `build_app()`; `test_help_lists_registered_commands` asserts 12-command list; per-command tests in `test_control_commands.py`, `test_safety_commands.py`, `test_settings_command.py` green |
| SAFE-04: `/pause` writes `SafetyEventRecord(kind='pause')` atomically; narrates `[SAFETY] Paused.` | ✓ PASS | `PauseCommand.handle()` calls `service.log_pause()`; `SafetyEventService._log()` uses `with self.conn:` atomic INSERT; `test_pause_persists_safety_event` confirms DB row and narration line |
| SAFE-05: `/line <topic>` writes `SafetyEventRecord(kind='line', policy_ref=<topic>)`; narrates redline | ✓ PASS | `LineCommand.handle()` calls `service.log_line()`; `test_line_persists_safety_event_with_topic`, `test_line_with_multi_word_topic_joins_args` green |
| SAFE-06: All Phase 3 safety events schema-locked to `visibility='player_visible'`; secret-shaped payloads rejected | ✓ PASS | SQL CHECK constraint `visibility IN ('player_visible')`; `SafetyEventService._log()` scans via `RedactionCanary`; `test_safety_events_check_visibility_rejects_gm_only`, `test_log_event_rejected_if_secret_shaped`, `test_line_rejects_secret_shaped_topic` all green |
| Stub phase-ownership: save/recap/sheet/inventory/map/retcon each name future phase owner | ✓ PASS | Each stub command emits a narration line containing the owning phase (Phase 4/5/7/8); `test_each_stub_command_appends_expected_prefix` green |
| COST-05 UI: `/budget` renders `BudgetInspection` from runtime `CostGovernor` | ✓ PASS | `BudgetCommand.handle()` reads `app.cost_governor.format_budget_inspection()`; `test_budget_command_with_governor_renders_inspection` green |
| ONBD-05 cross-plan: `/settings` reads committed triples without touching them | ✓ PASS | `SettingsCommand.handle()` calls `app.onboarding_store.reload(campaign_id)`; `test_settings_with_triple_renders_summary` green |
| Migration 0004 applies cleanly; schema reaches v4 | ✓ PASS | `safety_events` table present; `apply_migrations` returns `[1,2,3,4]`; `test_migration_0004_creates_safety_events_table` green |

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/sagasmith/app/paths.py` | `CampaignPaths` + `resolve_campaign_paths()` | ✓ VERIFIED | 1,356 bytes; `class CampaignPaths` present; wired via `init_cmd.py` → `init_campaign()` |
| `src/sagasmith/app/campaign.py` | `init_campaign`, `open_campaign`, `CampaignManifest` | ✓ VERIFIED | 5,691 bytes; `def init_campaign` present; wired from `init_cmd.py` |
| `src/sagasmith/app/config.py` | `SettingsRepository` with RedactionCanary-guarded put | ✓ VERIFIED | 2,847 bytes; `class SettingsRepository` present; `RedactionCanary` guard in `put()` confirmed |
| `src/sagasmith/schemas/campaign.py` | `CampaignManifest` + `ProviderSettings` | ✓ VERIFIED | Exported from `schemas/__init__.py`; consumed by CLI and app layers |
| `src/sagasmith/cli/init_cmd.py` | `sagasmith init` command | ✓ VERIFIED | `def init_command` present; calls `init_campaign()`; wired in `cli/main.py` |
| `src/sagasmith/cli/play_cmd.py` | `sagasmith play` command → Textual TUI | ✓ VERIFIED | Calls `build_app(campaign).run()`; `--headless-status` flag preserved |
| `src/sagasmith/cli/configure_cmd.py` | `sagasmith configure` command | ✓ VERIFIED | `def configure_command` present; parses `SecretRef` descriptors; no secret echo |
| `src/sagasmith/persistence/migrations/0002_campaign_and_settings.sql` | `campaigns` + `settings` tables | ✓ VERIFIED | `CREATE TABLE IF NOT EXISTS campaigns` present; FK enforced |
| `src/sagasmith/persistence/migrations/0003_onboarding_records.sql` | Three onboarding tables with FK | ✓ VERIFIED | `onboarding_player_profile`, `onboarding_content_policy`, `onboarding_house_rules` all present |
| `src/sagasmith/persistence/migrations/0004_safety_events.sql` | `safety_events` table with CHECK constraints | ✓ VERIFIED | `visibility CHECK ('player_visible')`, `kind CHECK (...)`, FK to `campaigns` all present |
| `src/sagasmith/onboarding/wizard.py` | `OnboardingWizard` 9-phase state machine | ✓ VERIFIED | 18,445 bytes; `class OnboardingWizard` present; no Textual/CLI/SQLite imports |
| `src/sagasmith/onboarding/prompts.py` | `ONBOARDING_PHASES` catalog + `parse_answer()` | ✓ VERIFIED | 16,083 bytes; `ONBOARDING_PHASES` present; all 8 `PromptFieldKind` branches implemented |
| `src/sagasmith/onboarding/store.py` | `OnboardingStore` with atomic commit + re-run | ✓ VERIFIED | 6,100 bytes; `class OnboardingStore` present; `INSERT OR REPLACE` semantics; RedactionCanary scan added (post-review fix) |
| `src/sagasmith/tui/app.py` | `SagaSmithApp` Textual App subclass | ✓ VERIFIED | 5,061 bytes; four-region `compose()`; `on_unmount()` closes `_service_conn` (post-review fix) |
| `src/sagasmith/tui/widgets/narration.py` | `NarrationArea` append-only transcript widget | ✓ VERIFIED | `RichLog(markup=False)` prevents Rich injection (T-03-17 mitigated) |
| `src/sagasmith/tui/widgets/status_panel.py` | `StatusPanel` renders `StatusSnapshot` | ✓ VERIFIED | Reactive `snapshot` watcher; `_format_snapshot()` renders all 7 fields |
| `src/sagasmith/tui/widgets/safety_bar.py` | `SafetyBar` docked top bar | ✓ VERIFIED | `dock: top` CSS; shows /pause /line affordances |
| `src/sagasmith/tui/widgets/input_line.py` | `InputLine` Enter-submit handler | ✓ VERIFIED | Posts `Submitted` message on Enter; clears input field |
| `src/sagasmith/tui/state.py` | `StatusSnapshot` + `TUIState` (pure data) | ✓ VERIFIED | No Textual imports; `format_hp()`, `format_clock()` methods present |
| `src/sagasmith/tui/commands/registry.py` | `CommandRegistry` + `TUICommand` Protocol | ✓ VERIFIED | `class CommandRegistry` present; `dispatch()` writes unknown-command message to narration |
| `src/sagasmith/tui/runtime.py` | `build_app()` factory | ✓ VERIFIED | Opens campaign, registers all 12 commands, loads scrollback, binds services |
| `src/sagasmith/services/safety.py` | `SafetyEventService` with RedactionCanary guard | ✓ VERIFIED | 3,879 bytes; `log_pause`, `log_line`, `log_fallback`, `list_recent` present; deferred `RedactionCanary` import (circular import fix applied) |
| `src/sagasmith/persistence/repositories.py` | `SafetyEventRepository` appended | ✓ VERIFIED | `class SafetyEventRepository` present; `append` and `list_for_campaign` methods |
| `src/sagasmith/tui/commands/control.py` | 8 control commands (stubs + clock/budget) | ✓ VERIFIED | 3,888 bytes; `ClockCommand`, `BudgetCommand`, and 6 stubs all present |
| `src/sagasmith/tui/commands/safety.py` | `PauseCommand` + `LineCommand` | ✓ VERIFIED | Both call `app.safety_events.log_pause/log_line()` |
| `src/sagasmith/tui/commands/settings.py` | `SettingsCommand` reads `OnboardingStore` | ✓ VERIFIED | Calls `app.onboarding_store.reload(campaign_id)` and renders triple summary |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `cli/init_cmd.py` | `app/campaign.py::init_campaign` | CLI calls domain function | ✓ WIRED | `init_campaign(` found at line 62 of `init_cmd.py` |
| `app/campaign.py` | `persistence/migrations.py::apply_migrations` | `init_campaign` runs migrations before INSERT | ✓ WIRED | `apply_migrations(` present in `campaign.py` |
| `app/config.py` | `services/secrets.py::SecretRef` | `SettingsRepository` stores `SecretRef` descriptors | ✓ WIRED | `SecretRef` imported and used in `config.py` |
| `cli/main.py` | `cli/init_cmd.py` | `app.command("init")(init_command)` registration | ✓ WIRED | `sagasmith --help` confirms `init`, `play`, `configure`, `demo` all listed |
| `cli/play_cmd.py` | `tui/runtime.py::build_app` | `play_command` calls `build_app(campaign).run()` | ✓ WIRED | Confirmed in `play_cmd.py` |
| `tui/runtime.py` | `app/campaign.py::open_campaign` | Runtime validates campaign before constructing app | ✓ WIRED | `open_campaign(` present in `runtime.py` line 44 |
| `tui/commands/safety.py` | `services/safety.py::SafetyEventService` | Pause/Line commands call `log_pause`/`log_line` | ✓ WIRED | `app.safety_events.log_pause(...)` and `app.safety_events.log_line(...)` found in `safety.py` |
| `services/safety.py` | `evals/redaction.py::RedactionCanary` | Every event JSON scanned before INSERT | ✓ WIRED | Deferred `_default_canary()` factory confirmed; `RedactionCanary` instance scans in `_log()` |
| `tui/commands/settings.py` | `onboarding/store.py::OnboardingStore` | `SettingsCommand` reloads triple | ✓ WIRED | `store.reload(app.manifest.campaign_id)` at line 28 of `settings.py` |
| `tui/runtime.py` | `tui/commands/*.py` | `build_app` registers all 12 commands via `registry.register` | ✓ WIRED | `registry.register(cmd)` loop at line 75 of `runtime.py`; confirmed 12 commands |
| `tui/commands/control.py::BudgetCommand` | `services/cost.py::CostGovernor` | `/budget` reads `app.cost_governor.format_budget_inspection()` | ✓ WIRED | `app.cost_governor` slot set in `build_app()`; `BudgetCommand.handle()` reads it |
| `onboarding/wizard.py` | `schemas/player.py::PlayerProfile/ContentPolicy/HouseRules` | `build_records()` constructs validated Pydantic models | ✓ WIRED | `PlayerProfile(`, `ContentPolicy(`, `HouseRules(` all found in `wizard.py` |

---

## Data-Flow Trace (Level 4)

Phase 3 artifacts are primarily CLI commands, TUI widgets, domain services, and persistence layers — not dashboard-style components with dynamic data. The following key flows are confirmed wired and non-hollow:

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `PauseCommand.handle()` | `record` (SafetyEventRecord) | `SafetyEventService.log_pause()` → SQLite INSERT | Yes — DB write + return confirmed by `test_pause_persists_safety_event` | ✓ FLOWING |
| `LineCommand.handle()` | `record` (SafetyEventRecord) | `SafetyEventService.log_line()` → SQLite INSERT | Yes — policy_ref and action_taken populated from user input | ✓ FLOWING |
| `SettingsCommand.handle()` | `triple` (OnboardingTriple) | `OnboardingStore.reload()` → SQLite SELECT | Yes — returns `None` (no onboarding) or validated triple; rendered to narration | ✓ FLOWING |
| `BudgetCommand.handle()` | `inspection` (BudgetInspection) | `CostGovernor.format_budget_inspection()` | Yes — real BudgetInspection with session_budget/spent/fraction; `None` guard when no governor | ✓ FLOWING |
| `NarrationArea._load_scrollback` (via `build_app`) | `lines` | `transcript_entries` SQLite query | Yes — `ORDER BY id DESC LIMIT 50`; empty list on fresh campaign | ✓ FLOWING |
| `StatusPanel.snapshot` | `StatusSnapshot` | `TUIState.status` (set in `on_mount`) | Default (all None/empty) in Phase 3 — Phase 4 wires graph state → TUIState | ⚠️ STATIC (by design; Phase 4 deferred) |

The `StatusPanel.snapshot` default-only status is intentional — Phase 3 establishes the rendering pipeline; Phase 4 (Graph Runtime) bridges `SagaState` → `TUIState`. This is documented in `03-03-PLAN.md` and `03-04-PLAN.md` explicitly as deferred to Phase 4.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `sagasmith --help` lists init/play/configure/demo/smoke/schema/version | `uv run sagasmith --help` | All 7 commands listed | ✓ PASS |
| Smoke suite passes 12/12 checks without paid calls | `uv run sagasmith smoke --mode fast` | `12/12 checks passed` | ✓ PASS |
| Full test suite green | `uv run pytest -q` | `295 passed, 1 skipped` | ✓ PASS |
| Ruff lint clean | `uv run ruff check src tests` | `All checks passed!` | ✓ PASS |
| Pyright (Phase 3 src files) | `uv run pyright src tests` | 1 error in `tui/runtime.py:49` (`_service_conn` protected access); 12 errors in pre-Phase-2 test files | ⚠️ WARN (see note) |

**Pyright error note:** The single Phase-3-introduced pyright error is `src/sagasmith/tui/runtime.py:49: "_service_conn" is protected and used outside of class` (reportPrivateUsage). This is an intentional architectural pattern: `build_app()` in `runtime.py` is the designated builder/owner of `SagaSmithApp`, acting as a factory that must initialize protected lifecycle state. The fix was applied per `03-REVIEW-FIX.md` (CR-01): `_service_conn` is declared in `SagaSmithApp.__init__` as `_service_conn: sqlite3.Connection | None = None` and `on_unmount()` closes it. The `runtime.py` setter (`app._service_conn = service_conn`) is the only cross-module access. The 12 pre-existing pyright errors all originate in Phase 2 test files (`test_transport.py`, `test_fake_client.py`, `test_openrouter_client.py`, `test_secrets.py`, `test_turn_close.py`, `test_fixture_override_validation.py`) and are pre-existing, not introduced by Phase 3.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CLI-01 | 03-01 | `sagasmith init` creates campaign.sqlite, player_vault/, campaign.toml | ✓ SATISFIED | `init_campaign()` wired from `init_cmd.py`; smoke check #12 passes |
| CLI-02 | 03-01 | User chooses/confirms campaign name and path (TTY or flags) | ✓ SATISFIED | `isatty()` guard in `init_cmd.py`; `test_init_requires_name_in_non_interactive_mode` green |
| CLI-03 | 03-01/03-03 | `sagasmith play` starts/resumes without hosted server | ✓ SATISFIED | `play_cmd.py` calls `build_app().run()`; no network dependency |
| CLI-05 | 03-01 | Demo/smoke mode uses fixtures; no paid calls | ✓ SATISFIED | `demo` command calls `run_smoke()`; 12/12 smoke checks pass without network |
| ONBD-01 | 03-02 | 9-phase onboarding captures all required fields | ✓ SATISFIED | `ONBOARDING_PHASES` covers all fields; `test_wizard_happy_path_reaches_done` green |
| ONBD-02 | 03-02 | Hard limits, soft limits, preferences captured | ✓ SATISFIED | `ContentPolicy` schema + CONTENT_POLICY phase; validated by Pydantic |
| ONBD-03 | 03-02 | Review and edit before commit | ✓ SATISFIED | `OnboardingWizard.review()`, `edit()`, REVIEW phase state machine |
| ONBD-04 | 03-02 | Validated triple persists atomically before gameplay | ✓ SATISFIED | `OnboardingStore.commit()` uses `with self.conn:` + FK enforcement |
| ONBD-05 | 03-02/03-04 | Re-run onboarding without deleting campaign | ✓ SATISFIED | `INSERT OR REPLACE` in `commit()`; `/settings` reads without overwriting |
| TUI-01 | 03-03 | Textual interface with narration, status, safety bar, input | ✓ SATISFIED | Four-region `compose()`; `test_app_mounts_with_four_regions` green |
| TUI-02 | 03-03 | Natural-language input echoes to narration | ✓ SATISFIED | `on_player_input_submitted()` appends `> {text}`; `test_freeform_input_echoes_to_narration` green |
| TUI-03 | 03-03 | Scroll/review completed transcript entries | ✓ SATISFIED | `_load_scrollback()` reads up to 50 entries from SQLite; `test_scrollback_loads_on_mount` green |
| TUI-04 | 03-03 | Status panel shows HP, conditions, quest, location, clock, rolls | ✓ SATISFIED | `StatusPanel._format_snapshot()` renders all 7 fields; state tests green |
| TUI-05 | 03-03 | `/help` shows supported commands and descriptions | ✓ SATISFIED | `HelpCommand` auto-discovers registered commands; `test_slash_help_dispatches_and_appends_help` green |
| TUI-06 | 03-04 | All 12 slash commands available and listed | ✓ SATISFIED | 12 commands registered in `build_app()`; `test_help_lists_registered_commands` confirms all 12 |
| SAFE-04 | 03-04 | `/pause` freezes play; persisted safety event | ✓ SATISFIED | `PauseCommand` → `SafetyEventService.log_pause()` → atomic INSERT; `test_pause_persists_safety_event` green |
| SAFE-05 | 03-04 | `/line` mid-scene redlines content; narration rerouted | ✓ SATISFIED | `LineCommand` → `SafetyEventService.log_line()` with `policy_ref`; narration confirms redline |
| SAFE-06 | 03-04 | Safety events logged without secrets or GM-only spoilers | ✓ SATISFIED | `visibility CHECK ('player_visible')` constraint; RedactionCanary scans all event JSON; `test_safety_events_check_visibility_rejects_gm_only` and `test_line_rejects_secret_shaped_topic` green |

**All 18 Phase 3 requirement IDs (CLI-01/02/03/05, ONBD-01..05, TUI-01..06, SAFE-04/05/06) are SATISFIED.**

---

## Anti-Patterns Found

| File | Finding | Severity | Impact |
|------|---------|----------|--------|
| `src/sagasmith/tui/commands/control.py` | `SaveCommand`, `RecapCommand`, `SheetCommand`, `InventoryCommand`, `MapCommand`, `RetconCommand` handlers return stubs | ℹ️ INFO | **Intentional by design** — each stub names its owning future phase (Phase 4/5/7/8); this is the documented pattern per `03-04-PLAN.md`; verified by `test_each_stub_command_appends_expected_prefix` |
| `src/sagasmith/tui/widgets/narration.py` | `load_scrollback()` method dead code (noted in 03-REVIEW.md as MR-02) | ⚠️ WARNING | Does not affect goal; `on_mount` uses `append_line()` loop correctly; `logged_lines` stays consistent |
| `src/sagasmith/tui/runtime.py:49` | `app._service_conn` protected attribute access from outside class | ⚠️ WARNING | Single pyright error; intentional factory-owns-lifecycle pattern; `on_unmount()` correctly closes; tests pass |

**No blocker anti-patterns found.** The stub commands are intentional per-plan design (not hollow implementations that should be real). The `load_scrollback()` dead method is a minor quality issue, not a correctness issue.

---

## SUMMARY.md Existence Check

| Plan | SUMMARY.md | Non-trivial | Self-Check |
|------|-----------|-------------|-----------|
| 03-01 | ✓ EXISTS | ✓ Yes (191 lines; full accomplishments, decisions, deviations) | PASSED |
| 03-02 | ✓ EXISTS | ✓ Yes (179 lines; full accomplishments, decisions, deviations) | PASSED |
| 03-03 | ✓ EXISTS | ✓ Yes (208 lines; full accomplishments, decisions, deviations) | PASSED |
| 03-04 | ✓ EXISTS | ✓ Yes (227 lines; full accomplishments, decisions, deviations) | PASSED |

---

## Human Verification Required

### 1. TUI Interactive Launch

**Test:** Run `uv run sagasmith init --name "Verify" --path ./tmp-verify --provider fake` then `uv run sagasmith play --campaign ./tmp-verify`
**Expected:** Textual TUI launches in terminal with four visible regions; typing `/help` shows 12 commands alphabetically; typing `/pause` narrates `[SAFETY] Paused. (event safety_...)`; Ctrl+Q exits cleanly
**Why human:** Textual requires a real terminal; `run_test()` pilot tests confirm logic but not visual rendering, responsive layout, or WAL checkpoint-on-clean-exit behavior

### 2. Safety Event Persistence End-to-End

**Test:** In the launched TUI (from test 1), type `/line graphic violence`, press Enter, then Ctrl+Q; run `sqlite3 ./tmp-verify/campaign.sqlite "SELECT kind, policy_ref, action_taken, visibility FROM safety_events;"`
**Expected:** One row: `line|graphic violence|redlined:graphic violence|player_visible`
**Why human:** Confirms the complete chain from TUI keystroke → `LineCommand` → `SafetyEventService` → SQLite write is functional in an actual terminal session (vs. isolated unit test)

---

## Gaps Summary

No gaps blocking goal achievement. All 5 ROADMAP success criteria are verified, all 18 requirement IDs are satisfied, and all 4 plan SUMMARY.md files exist and are non-trivial.

Two human verification items remain: interactive TUI launch and safety-event end-to-end verification in a real terminal. These cannot be exercised programmatically without a PTY.

Post-review fixes confirmed applied (per `03-REVIEW-FIX.md`):
- **CR-01 (critical):** `on_unmount()` added to `SagaSmithApp` to close `_service_conn` on TUI exit — confirmed in `app.py` lines 117-126
- **HR-01 (high):** `RedactionCanary` scan added to `OnboardingStore.commit()` before INSERT — confirmed in `store.py`
- **HR-02 (high):** `pydantic.ValidationError` caught in `configure_cmd.py` and `init_cmd.py` — confirmed in both files
- **HR-03 (high):** `shutil.rmtree` cleanup on failed `init_campaign` — confirmed in `campaign.py`

All medium/low review findings are quality improvements, not goal blockers.

---

_Verified: 2026-04-27T16:02:31Z_
_Verifier: gsd-verifier (kilo/anthropic/claude-sonnet-4.6)_
