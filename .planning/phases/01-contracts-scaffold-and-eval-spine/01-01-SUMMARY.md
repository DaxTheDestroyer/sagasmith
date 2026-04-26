---
phase: 01-contracts-scaffold-and-eval-spine
plan: 01
subsystem: foundation-scaffold
tags: [python, uv, typer, ruff, pyright, pytest, pre-commit, gitleaks]

requires: []
provides:
  - uv-managed ai-sagasmith Python package scaffold with committed lockfile
  - sagasmith import package exposing __version__ and Typer console script
  - canonical Phase 1 subpackage layout for app, cli, tui, graph, agents, services, providers, persistence, memory, schemas, evals, and skills
  - quality gate configuration for ruff, pyright, pytest, pre-commit, gitleaks, and Makefile targets
affects: [phase-01-plan-02, phase-01-plan-03, all-python-implementation]

tech-stack:
  added: [Python 3.12.12, uv 0.9.24, Typer 0.25.0, Pydantic 2.13.3, pydantic-settings 2.14.0, Ruff 0.15.12, Pyright 1.1.409, pytest 8.4.2, pytest-asyncio 0.26.0, pre-commit 4.6.0]
  patterns:
    - src-layout Python package managed by uv and hatchling
    - Typer CLI app exported through pyproject console script
    - strict-ish pyright with warnings for third-party unknowns
    - ruff owns linting, formatting, and import sorting

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
    - ruff.toml
    - pyrightconfig.json
    - .pre-commit-config.yaml
    - Makefile
    - README.md
    - src/sagasmith/cli/main.py
    - tests/test_import_and_entry.py
  modified:
    - .gitignore

key-decisions:
  - "Kept Phase 1 dependencies minimal: Typer, Pydantic, and pydantic-settings at runtime; quality tools in the uv dev dependency group."
  - "Preserved existing .gitignore coverage while adding plan-required Python, uv, cache, env, and SQLite ignore entries."
  - "Documented Makefile targets even though make is not installed in this Windows shell; direct uv command equivalents were used for verification."

patterns-established:
  - "Every top-level SagaSmith subpackage has an __init__.py and a purpose docstring, but no premature domain modules."
  - "CLI entrypoints import the cheap sagasmith package root only for __version__, preserving side-effect-free package import."
  - "Smoke tests validate importability, CLI help, CLI version output, and canonical subpackage presence."

requirements-completed: [FOUND-01, FOUND-02, FOUND-03, FOUND-05]

duration: 48 min
completed: 2026-04-26
---

# Phase 1 Plan 01: Scaffold the SagaSmith Package Summary

**uv-managed Python package scaffold with canonical SagaSmith subpackages, Typer version CLI, quality gates, and developer run-book.**

## Performance

- **Duration:** 48 min
- **Started:** 2026-04-26T22:57:58Z
- **Completed:** 2026-04-26T23:45:58Z
- **Tasks:** 3/3 completed
- **Files modified:** 29 including this summary; 28 scaffold/tooling files before summary

## Accomplishments

- Created the `ai-sagasmith` uv project with a committed `uv.lock`, Python `>=3.12,<3.14`, and import package `sagasmith` exposing `__version__ = "0.0.1"`.
- Added the canonical subpackage layout: `app`, `cli`, `tui`, `graph`, `agents`, `services`, `providers`, `persistence`, `memory`, `schemas`, `evals`, and `skills`.
- Implemented a minimal Typer app with `sagasmith version`, `sagasmith --help`, and `python -m sagasmith` support.
- Added ruff, pyright, pre-commit/gitleaks, pytest marker, Makefile targets, and README commands for the Phase 1 developer workflow.
- Added import and CLI smoke tests covering package version alignment, CLI version output, CLI help, and all planned top-level subpackages.

## Task Commits

Each task was committed atomically where possible:

1. **Task 1 RED: Import and CLI smoke tests** - `4632faa` (`test`)
2. **Task 1 GREEN: uv package scaffold and subpackage layout** - `f4b8914` (`feat`)
3. **Task 2: Quality gate tooling** - `0280765` (`chore`)
4. **Task 3: Developer run-book** - `eb1b262` (`docs`)

**Plan metadata:** committed after self-check.

_Note: Task 1 was TDD, so it intentionally produced separate RED and GREEN commits._

## Files Created/Modified

- `.python-version` - Python baseline (`3.12`).
- `.gitignore` - Python/cache/env/SQLite ignore coverage while preserving existing local-tool ignores.
- `pyproject.toml` - PEP 621 project metadata, hatchling build backend, runtime/dev dependencies, console script, pytest config.
- `uv.lock` - Reproducible resolved dependency graph.
- `src/sagasmith/__init__.py` - Side-effect-free package root exposing `__version__`.
- `src/sagasmith/__main__.py` - Module execution bridge to the Typer app.
- `src/sagasmith/cli/main.py` - Typer app and `version` subcommand.
- `src/sagasmith/app/__init__.py` and `src/sagasmith/app/bootstrap.py` - App/bootstrap reserved modules.
- `src/sagasmith/{tui,graph,agents,services,providers,persistence,memory,schemas,evals,skills}/__init__.py` - Canonical package boundaries with purpose docstrings.
- `tests/__init__.py` and `tests/conftest.py` - Test package and shared-fixture reservation.
- `tests/test_import_and_entry.py` - Import and CLI smoke tests.
- `ruff.toml` - Ruff lint/format/import sorting configuration.
- `pyrightconfig.json` - Strict-ish pyright configuration.
- `.pre-commit-config.yaml` - Ruff, ruff-format, gitleaks, and local pyright hook definitions.
- `Makefile` - Documented install/lint/format/format-check/typecheck/test/smoke/precommit/clean targets.
- `README.md` - Fresh-checkout install, command, CLI, layout, planning, secrets, and license run-book.

## Final Subpackage List

- `sagasmith.app` — bootstrap, config, session identity, dependency wiring.
- `sagasmith.cli` — Typer command entry points.
- `sagasmith.tui` — Textual widgets, screens, and events.
- `sagasmith.graph` — LangGraph orchestration, routing, and thin graph nodes.
- `sagasmith.agents` — prompts and per-agent adapters.
- `sagasmith.services` — deterministic dice, PF2e rules, command dispatch, safety, cost, and validation.
- `sagasmith.providers` — LLM client contracts and provider implementations.
- `sagasmith.persistence` — SQLite repositories, migrations, and checkpoint wiring.
- `sagasmith.memory` — vault IO, projection, retrieval, and derived indices.
- `sagasmith.schemas` — Pydantic models and JSON Schema export.
- `sagasmith.evals` — deterministic replay, fixture, and smoke harnesses.
- `sagasmith.skills` — first-party Agent Skills registry and loading support.

## Tool Versions Verified

- Python: `3.12.12`
- uv: `0.9.24`
- Ruff: `0.15.12`
- Pyright: `1.1.409`
- pytest: `8.4.2`

## Verification

Plan verification commands passed, with one environment-specific note: `make` is not installed in this Windows shell, so Makefile target behavior was verified by running the equivalent documented direct `uv run` commands and checking Makefile target content.

- `uv sync --all-groups` — passed.
- `uv run ruff check src tests` — passed.
- `uv run ruff format --check src tests` — passed.
- `uv run pyright` — passed (`0 errors, 0 warnings, 0 informations`).
- `uv run pytest -q` — passed (`4 passed`).
- `uv run pytest -q -m smoke` — passed as an empty smoke selection (`4 deselected`); Plan 03 adds actual smoke tests.
- `uv run sagasmith version` — passed (`0.0.1`).
- `uv run sagasmith --help` — passed and displayed the Typer command list including `version`.
- `uv run python -c "import sagasmith; print(sagasmith.__version__)"` — passed (`0.0.1`).
- `uv run python -c "import sagasmith, sagasmith.app, sagasmith.cli, sagasmith.tui, sagasmith.graph, sagasmith.agents, sagasmith.services, sagasmith.providers, sagasmith.persistence, sagasmith.memory, sagasmith.schemas, sagasmith.evals, sagasmith.skills; print('ok')"` — passed (`ok`).

## Decisions Made

- Followed the plan's minimal dependency envelope instead of adding the larger research stack early; Textual, LangGraph, HTTPX, keyring, LanceDB, NetworkX, and PF2e-specific dependencies remain deferred to the plans that first use them.
- Preserved pre-existing `.gitignore` entries while satisfying the plan-required ignore list, to avoid removing unrelated local-tool/editor/log protections.
- Treated lack of `make` in the current Windows shell as an environment limitation, not a project blocker, because README and Makefile targets are present and their direct `uv run` equivalents pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved existing `.gitignore` protections while adding plan-required entries**
- **Found during:** Task 1 (Create `pyproject.toml`, subpackage tree, and `uv` lockfile)
- **Issue:** Replacing `.gitignore` verbatim with only the plan list would have removed existing local-tool, editor, Node, logs, and packaging ignore coverage.
- **Fix:** Added all plan-required entries while preserving prior ignore rules.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` showed generated `.venv` and `.claude` files ignored; Task 1 verification passed.
- **Committed in:** `f4b8914`

**2. [Rule 1 - Bug] Adjusted Typer app registration for subcommand behavior**
- **Found during:** Task 1 automated verification
- **Issue:** With only one Typer command registered, Typer treated `version` as a root command argument and `uv run sagasmith version` failed with "Got unexpected extra argument (version)".
- **Fix:** Added an app callback so Typer keeps the `version` subcommand in command-group mode while preserving the required app help and command registration.
- **Files modified:** `src/sagasmith/cli/main.py`
- **Verification:** `uv run sagasmith version`, `uv run sagasmith --help`, and `uv run pytest tests/test_import_and_entry.py -x` passed.
- **Committed in:** `f4b8914`

**3. [Rule 3 - Blocking] Applied ruff import sorting before quality gate commit**
- **Found during:** Task 2 verification
- **Issue:** `uv run ruff check src tests` reported import-block formatting issues in `src/sagasmith/__main__.py` and `tests/test_import_and_entry.py`.
- **Fix:** Ran `uv run ruff check --fix src tests` and committed the formatting changes with quality tooling.
- **Files modified:** `src/sagasmith/__main__.py`, `tests/test_import_and_entry.py`
- **Verification:** `uv run ruff check src tests` and `uv run ruff format --check src tests` passed.
- **Committed in:** `0280765`

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking issue)
**Impact on plan:** All deviations preserved correctness or developer workflow stability without expanding runtime scope.

## Issues Encountered

- `gsd-sdk query ...` commands were unavailable in this environment; plan execution continued manually following the workflow file. STATE/ROADMAP/REQUIREMENTS updates are not included because the requested mode said not to update them unless the workflow explicitly requires it, and the available SDK did not support query handlers.
- `make` is not installed on this Windows shell. Makefile targets were created exactly as planned; direct command equivalents passed, and target contents were verified.
- Typer/Rich help output renders the em dash as a replacement character in this terminal capture, but the CLI exits 0 and tests assert the stable `sagasmith` help text.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `src/sagasmith/app/bootstrap.py:1` — Intentional Phase 1 reservation docstring: "Dependency wiring entry point. Populated in Phase 2+." No bootstrap behavior is required until deterministic services and runtime wiring exist.
- Empty top-level subpackage `__init__.py` files — Intentional package-boundary reservations for downstream plans; they do not block this scaffold's goal.

## Threat Flags

None. This plan introduced local developer commands, package metadata, and a CLI help/version surface only. It did not introduce network endpoints, secret handling code, file persistence beyond project tooling, or runtime trust-boundary changes beyond those already covered by the plan threat model.

## Next Phase Readiness

- Plan 02 can add Pydantic state contracts under the now-empty `sagasmith.schemas` package.
- The `sagasmith.schemas` package directory is intentionally empty and ready for Pydantic models plus JSON Schema export commands.
- Plan 03 can add actual no-paid-call smoke tests to the existing pytest `smoke` marker and `make smoke` command.

## Self-Check: PASSED

- Confirmed key created files exist: `pyproject.toml`, `uv.lock`, `.python-version`, `ruff.toml`, `pyrightconfig.json`, `.pre-commit-config.yaml`, `Makefile`, `README.md`, `src/sagasmith/cli/main.py`, and `tests/test_import_and_entry.py`.
- Confirmed all task commits exist: `4632faa`, `f4b8914`, `0280765`, and `eb1b262`.
- Re-ran final plan verification commands and import checks successfully.
- Confirmed working tree was clean before writing this summary.

---
*Phase: 01-contracts-scaffold-and-eval-spine*
*Completed: 2026-04-26*
