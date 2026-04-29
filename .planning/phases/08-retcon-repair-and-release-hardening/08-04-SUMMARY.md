---
phase: 08-retcon-repair-and-release-hardening
plan: 04
subsystem: testing
tags: [smoke, release-gate, cli, makefile, gitleaks]

requires:
  - phase: 07-memory-vault-and-resume
    provides: quit/resume persistence, player-vault repair surfaces, and later-process resume behavior
provides:
  - Layered in-process MVP no-paid-call smoke harness for install, init, configure, onboard, skill challenge, combat, quit, and resume
  - CLI `sagasmith smoke --mode mvp` entrypoint proof
  - `make release-gate` wrapper for lint, format check, typecheck, tests, MVP smoke, and secret scan
affects: [release-hardening, qa, smoke, cli]

tech-stack:
  added: []
  patterns:
    - Smoke checks return stable `SmokeCheck` names and sanitized details
    - Release gate composes existing project quality commands plus MVP smoke and gitleaks

key-files:
  created:
    - tests/evals/test_mvp_smoke.py
  modified:
    - src/sagasmith/evals/harness.py
    - src/sagasmith/cli/smoke_cmd.py
    - tests/evals/test_smoke_cli.py
    - Makefile

key-decisions:
  - "MVP smoke uses existing deterministic in-process APIs and fake provider settings, not OpenRouter credentials."
  - "The release gate uses the existing pre-commit gitleaks hook for secret scanning."

patterns-established:
  - "MVP smoke check names are exact QA contract names under the `mvp.*` namespace."
  - "Shell-level smoke coverage is tested through `uv run sagasmith smoke --mode mvp`."

requirements-completed: [QA-08, QA-09]

duration: 8 min
completed: 2026-04-29
---

# Phase 8 Plan 04: MVP Smoke and Release Gate Summary

**No-paid-call MVP smoke coverage with shell entrypoint proof and a release-blocking quality gate.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-29T17:05:50Z
- **Completed:** 2026-04-29T17:13:35Z
- **Tasks:** 3 completed
- **Files modified:** 5

## Accomplishments

- Added `run_mvp_smoke()` with eight observable checks: install/entrypoint, init, fake configure, onboarding, skill challenge, simple combat, quit, and resume.
- Added `SmokeMode.MVP` and verified the shell-level command `uv run sagasmith smoke --mode mvp` exits 0 and prints MVP check output.
- Added `secret-scan` and `release-gate` Make targets so release readiness wraps lint, format check, typecheck, tests, MVP smoke, and gitleaks.

## Task Commits

1. **Task 1: Add layered MVP smoke harness checks**
   - `6a0160c` test(08-04): add failing MVP smoke harness tests
   - `6970f63` feat(08-04): implement MVP smoke harness
2. **Task 2: Add CLI MVP smoke mode and shell-level entrypoint proof**
   - `8c352f2` test(08-04): add failing CLI MVP smoke mode tests
   - `91e43f1` feat(08-04): add CLI MVP smoke mode
3. **Task 3: Add release-gate Make target with secret scanning**
   - `ab285e4` feat(08-04): add release gate target
4. **Follow-up formatting commits**
   - `5356981` style(08-04): format MVP smoke imports
   - `788d4f5` style(08-04): format MVP smoke harness

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/evals/harness.py` - Adds the layered `run_mvp_smoke()` harness and sanitized MVP failure details.
- `src/sagasmith/cli/smoke_cmd.py` - Adds MVP smoke mode while preserving fast and pytest modes.
- `tests/evals/test_mvp_smoke.py` - Covers MVP harness check names, fake-provider/no-credential behavior, failure redaction, and release-gate Makefile wiring.
- `tests/evals/test_smoke_cli.py` - Covers `SmokeMode.MVP` and shell-level `uv run sagasmith smoke --mode mvp` execution.
- `Makefile` - Adds `secret-scan` and `release-gate` targets.

## Decisions Made

- MVP smoke uses deterministic in-process services and fake provider configuration so it never depends on OpenRouter credentials.
- Secret scanning is routed through `uv run pre-commit run gitleaks --all-files`, matching the existing project pre-commit convention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff formatting/import violations in new MVP smoke harness**
- **Found during:** Plan-level release-gate verification
- **Issue:** New harness imports and one long line failed ruff/import formatting checks.
- **Fix:** Applied ruff import fixes and ruff formatting to the touched harness file.
- **Files modified:** `src/sagasmith/evals/harness.py`, `tests/evals/test_mvp_smoke.py`
- **Verification:** `uv run ruff check src tests` passed; touched-file format check passed.
- **Committed in:** `5356981`, `788d4f5`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug).
**Impact on plan:** Formatting fixes were required for the planned release gate and did not change behavior.

## Issues Encountered

- `make release-gate` could not be executed in this Windows environment because no `make`, `mingw32-make`, or `gmake` executable is installed.
- Running the equivalent release-gate commands found pre-existing repository-wide failures outside this plan's scope:
  - `uv run ruff format --check src tests` reports 94 pre-existing files that would be reformatted.
  - `uv run pyright` reports pre-existing type errors, including `tests/services/test_safety_post_gate.py` and numerous existing strict-type warnings/errors.
  - `uv run pytest -q` reports 4 pre-existing failures from schema/migration count drift (`current_schema_version` expected 7 vs actual 8, schema count expected 29 vs actual 31, and missing Retcon/Vault audit schema expectations).

## Verification

- PASS: `uv run pytest tests/evals/test_mvp_smoke.py -x` — 4 passed.
- PASS: `uv run pytest tests/evals/test_smoke_cli.py -x` — 5 passed.
- PASS: `uv run pytest tests/evals/test_mvp_smoke.py tests/evals/test_smoke_cli.py -x` — 9 passed.
- PASS: `uv run ruff check src tests`.
- PASS: `uv run ruff format --check src/sagasmith/evals/harness.py src/sagasmith/cli/smoke_cmd.py tests/evals/test_mvp_smoke.py tests/evals/test_smoke_cli.py`.
- PASS: `uv run pyright src/sagasmith/evals/harness.py src/sagasmith/cli/smoke_cmd.py tests/evals/test_mvp_smoke.py tests/evals/test_smoke_cli.py`.
- PASS: `uv run sagasmith smoke --mode mvp` — 8/8 checks passed.
- PASS: `uv run pre-commit run gitleaks --all-files`.
- BLOCKED: `make release-gate` — `make` executable unavailable in the current environment.
- FAIL (pre-existing/out of scope): repository-wide `uv run ruff format --check src tests`, `uv run pyright`, and `uv run pytest -q` as detailed above.

## Known Stubs

None.

## Threat Flags

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

QA-08 and QA-09 implementation is complete for this plan. Phase 8 still has pending 08-02 and 08-03 retcon execution/UI plans, and repository-wide pre-existing quality failures must be resolved before `make release-gate` can pass end-to-end on a machine with `make` installed.

## Self-Check: PASSED

- Confirmed `tests/evals/test_mvp_smoke.py` exists.
- Confirmed implementation commits `6a0160c`, `6970f63`, `8c352f2`, `91e43f1`, `ab285e4`, `5356981`, and `788d4f5` exist in git history.
- Confirmed focused MVP smoke tests and CLI smoke tests pass.

---
*Phase: 08-retcon-repair-and-release-hardening*
*Completed: 2026-04-29*
