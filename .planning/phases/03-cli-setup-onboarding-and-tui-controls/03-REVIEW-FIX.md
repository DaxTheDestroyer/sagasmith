---
phase: 03-cli-setup-onboarding-and-tui-controls
fixed_at: 2026-04-27T16:00:00Z
review_path: .planning/phases/03-cli-setup-onboarding-and-tui-controls/03-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-04-27T16:00:00Z
**Source review:** .planning/phases/03-cli-setup-onboarding-and-tui-controls/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 critical + 3 high)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Service connection never closed (`runtime.py`)

**Files modified:** `src/sagasmith/tui/app.py`, `src/sagasmith/tui/runtime.py`
**Commit:** c692cca
**Applied fix:**
- Added `import sqlite3` to `app.py` imports.
- Added `self._service_conn: sqlite3.Connection | None = None` to `SagaSmithApp.__init__()`.
- Added `on_unmount(self) -> None` override to `SagaSmithApp` that closes and nullifies `self._service_conn`.
- In `runtime.build_app()`, assigned `app._service_conn = service_conn` immediately after opening the connection so the app owns its lifecycle.
- Unit tests that construct `SagaSmithApp` directly (bypassing `build_app`) are unaffected because `_service_conn` is initialized to `None` and `on_unmount` guards against `None`.

---

### HR-01: `OnboardingStore.commit()` bypasses RedactionCanary (`store.py`)

**Files modified:** `src/sagasmith/onboarding/store.py`
**Commit:** 6664aab
**Applied fix:**
- Added `from sagasmith.evals.redaction import RedactionCanary` import (alongside the already-imported `TrustServiceError`).
- Added a pre-commit canary scan loop in `commit()` that iterates over `("player_profile", ...), ("content_policy", ...), ("house_rules", ...)` JSON payloads before the `with self.conn:` block.
- Any `RedactionCanary` hit raises `TrustServiceError` with the record label and hit label in the message, consistent with the pattern in `SettingsRepository.put()`.
- The `with self.conn:` atomic INSERT block is unchanged; the scan fails before any DB writes occur.

---

### HR-02: Invalid `--provider` crashes with unhandled `ValidationError` (`configure_cmd.py`, `init_cmd.py`)

**Files modified:** `src/sagasmith/cli/configure_cmd.py`, `src/sagasmith/cli/init_cmd.py`
**Commit:** a3255ef
**Applied fix:**
- In `configure_cmd.py`: added `import pydantic`; wrapped the `ProviderSettings(...)` constructor in `try/except (pydantic.ValidationError, ValueError)` that echoes the error to stderr and raises `typer.Exit(code=2)`.
- In `init_cmd.py`: added `import pydantic`; added `except (pydantic.ValidationError, ValueError)` clause alongside the existing `except FileExistsError` on the `init_campaign(...)` call, printing a descriptive error and exiting with code 2.

---

### HR-03: Orphaned directory after failed `init_campaign` (`campaign.py`)

**Files modified:** `src/sagasmith/app/campaign.py`
**Commit:** 6f9d4a0
**Applied fix:**
- Added `import shutil` to module imports.
- Wrapped all post-`root.mkdir()` operations in a `try/except BaseException:` block.
- The except branch calls `shutil.rmtree(root, ignore_errors=True)` then re-raises, ensuring a clean retry path for the user.
- The inner `try/finally: conn.close()` is preserved inside the outer guard so the DB connection is still closed before cleanup.
- Existing `test_init_campaign_fails_when_dir_exists` test verifies `FileExistsError` is still raised when the directory pre-exists (the outer `root.mkdir()` fires before the cleanup guard, so this test is unaffected).

---

## Test Results

Post-fix full test run: **295 passed, 1 skipped** (`tests/providers/test_openrouter_client.py` live call opt-in skip — expected).

```
uv run pytest tests/ -x -q
295 passed, 1 skipped in 16.88s
```

---

_Fixed: 2026-04-27T16:00:00Z_
_Fixer: gsd-code-fixer (anthropic/claude-sonnet-4.6)_
_Iteration: 1_
