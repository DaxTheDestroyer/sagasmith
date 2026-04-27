---
phase: 03-cli-setup-onboarding-and-tui-controls
plan: 03
subsystem: tui
tags: [textual, tui, widgets, command-registry, sqlite, python, cli]

# Dependency graph
requires:
  - phase: 03-cli-setup-onboarding-and-tui-controls
    provides: CampaignPaths, open_campaign, init_campaign, open_campaign_db, play_cmd stub (Plan 03-01)
  - phase: 02-deterministic-trust-services
    provides: TranscriptRepository, open_campaign_db, transcript_entries table
provides:
  - SagaSmithApp (Textual App subclass) — four-region layout (narration, status, safety, input)
  - NarrationArea widget — RichLog-backed append-only transcript with markup=False (T-03-17)
  - StatusPanel widget — renders StatusSnapshot dataclass (HP, conditions, quest, location, clock, rolls)
  - SafetyBar widget — docked top bar showing /pause /line affordances
  - InputLine widget — Enter-submit handler posting Submitted message
  - PlayerInputSubmitted + CommandInvoked Textual Message types
  - StatusSnapshot + TUIState dataclasses (pure data, no Textual imports)
  - CommandRegistry + TUICommand Protocol — sole extension point for slash commands
  - HelpCommand — built-in /help lists all registered commands automatically
  - TUIRuntime.build_app() — opens campaign, registers /help, loads 50-line scrollback from SQLite
  - sagasmith play upgraded from stub to Textual TUI launch; --headless-status preserves test contract
  - 22 new TUI tests (state, mount, registry, help, input routing including TUI-02/03/05/T-03-17)
affects:
  - 03-04-PLAN.md (registers concrete commands via CommandRegistry.register(); no app.py changes needed)
  - Phase 4 (graph runtime wires SagaState to TUIState.status via StatusSnapshot updates)
  - Phase 5 (PF2e slice updates StatusPanel via StatusSnapshot from rules engine)
  - Phase 6 (AI GM loop streams narration to NarrationArea.append_line())
  - Phase 7 (memory/vault may use scrollback history for /recap)

# Tech tracking
tech-stack:
  added:
    - textual>=0.79,<1 (Textual TUI framework, pinned <1 to avoid 1.x API churn)
  patterns:
    - RichLog(markup=False) for narration — prevents Rich escape-sequence injection from transcript content
    - CommandRegistry as sole extension point — Plan 03-04 adds ~12 commands with zero changes to app.py
    - TUICommand Protocol with @runtime_checkable — duck-typed dispatch, no ABC inheritance required
    - build_app() factory — separates app construction (testable) from app.run() (blocking, CLI-only)
    - --headless-status flag — preserves pre-TUI test contracts after CLI upgrade (avoids TTY in CI)
    - frozen dataclass for StatusSnapshot — prevents accidental mutation of read-only game state snapshot
    - _load_scrollback() uses whitelist kind check — T-03-18: unknown kinds render as [content] not crash

key-files:
  created:
    - src/sagasmith/tui/state.py
    - src/sagasmith/tui/app.py
    - src/sagasmith/tui/widgets/__init__.py
    - src/sagasmith/tui/widgets/narration.py
    - src/sagasmith/tui/widgets/status_panel.py
    - src/sagasmith/tui/widgets/safety_bar.py
    - src/sagasmith/tui/widgets/input_line.py
    - src/sagasmith/tui/commands/__init__.py
    - src/sagasmith/tui/commands/registry.py
    - src/sagasmith/tui/commands/help.py
    - src/sagasmith/tui/runtime.py
    - tests/tui/__init__.py
    - tests/tui/test_state.py
    - tests/tui/test_app_mount.py
    - tests/tui/test_command_registry.py
    - tests/tui/test_help_command.py
    - tests/tui/test_input_routing.py
  modified:
    - pyproject.toml (added textual dependency)
    - uv.lock (regenerated with textual + linkify-it-py + mdit-py-plugins + uc-micro-py)
    - src/sagasmith/tui/__init__.py (re-exports SagaSmithApp, build_app, CommandRegistry, etc.)
    - src/sagasmith/cli/play_cmd.py (launches Textual TUI; --headless-status for test compat)
    - tests/cli/test_play_cmd.py (updated to pass --headless-status per Plan 03-03 contract)

key-decisions:
  - "textual>=0.79,<1 pinned with upper bound to avoid 1.x API churn without review"
  - "RichLog(markup=False) used for NarrationArea to prevent Rich markup injection (T-03-17)"
  - "CommandRegistry is the only extension point; zero app.py changes needed for new commands"
  - "build_app() factory separates construction (testable) from app.run() (blocking, CLI)"
  - "--headless-status flag preserves Plan 03-01 test contract after play_cmd TUI upgrade"
  - "StatusPanel._format_snapshot() (not _render) avoids override conflict with Widget._render()"
  - "BINDINGS: ClassVar = [...] with type: ignore[assignment] satisfies both ruff and pyright"
  - "Subclass-override pattern used for CommandInvoked capture in tests (monkey-patch doesn't work with Textual message dispatch)"

patterns-established:
  - "build_app() factory: open_campaign → SagaSmithApp → CommandRegistry → load_scrollback → return app"
  - "TUICommand Protocol: name + description + handle(app, args) — all implementations are frozen dataclasses"
  - "CommandRegistry.dispatch() writes unknown-command error to narration; no exceptions escape"
  - "_load_scrollback() caps at SCROLLBACK_LIMIT=50 (T-03-20) and whitelists kind column (T-03-18)"

requirements-completed:
  - TUI-01
  - TUI-02
  - TUI-03
  - TUI-04
  - TUI-05

# Metrics
duration: 12min
completed: 2026-04-27
---

# Phase 3 Plan 03: Textual TUI Shell Summary

**Textual SagaSmithApp with four-region layout, CommandRegistry protocol, built-in /help, TUIRuntime.build_app() with 50-line SQLite scrollback, and sagasmith play upgraded from stub to full TUI launch — 262 tests green, TUI-01 through TUI-05 verified end-to-end.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-27T15:03:11Z
- **Completed:** 2026-04-27T15:15:14Z
- **Tasks:** 2 completed
- **Files modified:** 20

## Accomplishments

- `SagaSmithApp` mounts four named regions (`#narration-area`, `#status-panel`, SafetyBar by type, `#input-line`) with zero paid LLM calls (TUI-01)
- Free-form input echoes as `> {text}` to narration and populates `TUIState.scrollback`; slash input parses name + args into `CommandInvoked` message (TUI-02)
- `_load_scrollback()` reads last 50 `transcript_entries` rows on mount; scrollback rendered chronologically with kind-specific prefixes (TUI-03)
- `StatusPanel` renders `StatusSnapshot` dataclass (HP, conditions, quest, location, clock, last rolls) via reactive watcher (TUI-04)
- `CommandRegistry` + `HelpCommand` — `/help` lists all registered commands; auto-discovers Plan 03-04 additions without app.py changes (TUI-05)
- `sagasmith play` upgraded from status-line stub to Textual TUI; `--headless-status` flag preserves Plan 03-01 test contract in CI
- T-03-17 mitigated: `RichLog(markup=False)` prevents Rich markup injection from transcript content
- T-03-18 mitigated: `_load_scrollback()` kind whitelist prevents crash on unknown transcript kinds

## Task Commits

Each task was committed atomically:

1. **Task 1: Textual dep + TUI widgets + SagaSmithApp layout (TUI-01, TUI-04)** - `cfb8ba3` (feat)
2. **Task 2: CommandRegistry + HelpCommand + TUIRuntime + play upgrade (TUI-02,03,05)** - `d8a1331` (feat)

## Files Created/Modified

- `src/sagasmith/tui/state.py` — StatusSnapshot (frozen dataclass) + TUIState (mutable UI state)
- `src/sagasmith/tui/app.py` — SagaSmithApp root layout; PlayerInputSubmitted + CommandInvoked messages
- `src/sagasmith/tui/widgets/narration.py` — NarrationArea (RichLog, markup=False)
- `src/sagasmith/tui/widgets/status_panel.py` — StatusPanel with reactive snapshot watcher
- `src/sagasmith/tui/widgets/safety_bar.py` — SafetyBar docked top bar
- `src/sagasmith/tui/widgets/input_line.py` — InputLine with Submitted message on Enter
- `src/sagasmith/tui/widgets/__init__.py` — re-exports all four widgets
- `src/sagasmith/tui/commands/registry.py` — CommandRegistry + TUICommand Protocol
- `src/sagasmith/tui/commands/help.py` — HelpCommand (auto-lists registered commands)
- `src/sagasmith/tui/commands/__init__.py` — re-exports registry/help/protocol
- `src/sagasmith/tui/runtime.py` — build_app() factory + _load_scrollback()
- `src/sagasmith/tui/__init__.py` — updated to re-export all public TUI types
- `pyproject.toml` — added textual>=0.79,<1 dependency
- `uv.lock` — regenerated with textual 0.89.1 + three transitive deps
- `src/sagasmith/cli/play_cmd.py` — upgraded to launch Textual TUI; --headless-status flag
- `tests/cli/test_play_cmd.py` — updated to pass --headless-status per Plan 03-03 contract
- `tests/tui/test_state.py` — 6 StatusSnapshot/TUIState unit tests
- `tests/tui/test_app_mount.py` — 5 async mount/input/slash tests via run_test()
- `tests/tui/test_command_registry.py` — 5 registry tests (4 unit + 1 async dispatch)
- `tests/tui/test_help_command.py` — 2 async /help listing tests
- `tests/tui/test_input_routing.py` — 4 async end-to-end TUI-02/03/05/T-03-17 tests

## Decisions Made

- `textual>=0.79,<1` upper bound pinned to avoid breaking API changes in Textual 1.x without review
- `RichLog(markup=False)` chosen to prevent stored-XSS-equivalent injection from transcript content (T-03-17)
- `StatusPanel._format_snapshot()` renamed from `_render()` to avoid override conflict with `Widget._render()`
- Subclass-override pattern used in tests for CommandInvoked capture — Textual message dispatch doesn't allow runtime monkey-patching of `on_*` handlers
- `BINDINGS: ClassVar = [...]` with `# type: ignore[assignment]` satisfies both ruff RUF012 and pyright's BINDINGS type constraint
- `--headless-status` flag added to `sagasmith play` to preserve Plan 03-01 test contract; flag is `hidden=True` to keep it out of `--help` output

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Monkey-patch approach for CommandInvoked capture failed in test**
- **Found during:** Task 1 (test_app_mount.py writing)
- **Issue:** Plan suggested monkey-patching `app.on_command_invoked` to capture events, but Textual dispatches messages via its own event loop — runtime attribute assignment doesn't intercept message handlers
- **Fix:** Used subclass-override pattern (`class CapturingApp(SagaSmithApp)`) to override `on_command_invoked` before `run_test()` is called
- **Files modified:** `tests/tui/test_app_mount.py`
- **Verification:** `test_input_submit_with_slash_parses_name_and_args` passes, confirming CommandInvoked is correctly captured
- **Committed in:** `cfb8ba3` (Task 1 commit)

**2. [Rule 1 - Bug] StatusPanel._render() name conflicts with Widget._render()**
- **Found during:** Task 1 (pyright check)
- **Issue:** pyright reported `_render` overrides Widget's `_render` method with incompatible signature (different arg count and return type)
- **Fix:** Renamed to `_format_snapshot()` — semantically clearer and avoids the override conflict
- **Files modified:** `src/sagasmith/tui/widgets/status_panel.py`
- **Verification:** pyright 0 errors after rename
- **Committed in:** `cfb8ba3` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep. All plan success criteria met.

## Issues Encountered

None — all tests pass, all verification commands clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `CommandRegistry.register(TUICommand)` is the sole extension point for Plan 03-04 — ~12 commands with zero changes to `app.py`
- `build_app(campaign_root)` factory is ready for Plan 03-04 to extend before calling `.run()`
- `NarrationArea.append_line()` and `StatusPanel.snapshot` reactive are ready for Phase 4 graph runtime to push updates
- All TUI-01 through TUI-05 requirements met and test-verified
- No paid LLM calls in any TUI lifecycle path (mount, input, command dispatch) — confirmed by zero mock/stub setup in TUI tests

---
*Phase: 03-cli-setup-onboarding-and-tui-controls*
*Completed: 2026-04-27*

## Self-Check: PASSED
