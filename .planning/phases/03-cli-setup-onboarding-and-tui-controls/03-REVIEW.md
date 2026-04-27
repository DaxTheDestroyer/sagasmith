---
phase: 03-cli-setup-onboarding-and-tui-controls
reviewed: 2026-04-27T16:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - src/sagasmith/app/__init__.py
  - src/sagasmith/app/bootstrap.py
  - src/sagasmith/app/campaign.py
  - src/sagasmith/app/config.py
  - src/sagasmith/app/paths.py
  - src/sagasmith/onboarding/__init__.py
  - src/sagasmith/onboarding/prompts.py
  - src/sagasmith/onboarding/store.py
  - src/sagasmith/onboarding/wizard.py
  - src/sagasmith/tui/__init__.py
  - src/sagasmith/tui/app.py
  - src/sagasmith/tui/runtime.py
  - src/sagasmith/tui/state.py
  - src/sagasmith/tui/commands/__init__.py
  - src/sagasmith/tui/commands/control.py
  - src/sagasmith/tui/commands/help.py
  - src/sagasmith/tui/commands/registry.py
  - src/sagasmith/tui/commands/safety.py
  - src/sagasmith/tui/commands/settings.py
  - src/sagasmith/tui/widgets/input_line.py
  - src/sagasmith/tui/widgets/narration.py
  - src/sagasmith/tui/widgets/safety_bar.py
  - src/sagasmith/tui/widgets/status_panel.py
  - src/sagasmith/cli/main.py
  - src/sagasmith/cli/configure_cmd.py
  - src/sagasmith/cli/init_cmd.py
  - src/sagasmith/cli/play_cmd.py
  - src/sagasmith/persistence/db.py
  - src/sagasmith/persistence/migrations.py
  - src/sagasmith/persistence/migrations/0003_onboarding_records.sql
  - src/sagasmith/persistence/migrations/0004_safety_events.sql
  - src/sagasmith/persistence/repositories.py
  - src/sagasmith/services/safety.py
findings:
  critical: 1
  high: 3
  medium: 5
  low: 3
  total: 12
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-27T16:00:00Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Phase 3 delivers the CLI setup (`init`, `play`, `configure`), the nine-phase onboarding wizard, the Textual TUI shell, and the `SafetyEventService`. The overall structure is clean and the trust-boundary invariants (RedactionCanary on every write path, `with conn:` atomicity, `markup=False` in `RichLog`) are largely followed correctly. Tests are thorough and the SAFE-04/05/06 contracts are well-exercised.

Three correctness issues require attention before promotion: a resource leak on the long-lived service connection, missing canary scan on onboarding commit (breaking the project-wide invariant), and uncaught `ValidationError` on invalid `--provider` input. The remaining findings are medium/low quality issues.

---

## Findings Table

| severity | file | line | finding | recommendation |
|----------|------|------|---------|----------------|
| critical | `src/sagasmith/tui/runtime.py` | 48 | **Service connection never closed** — `service_conn` opened in `build_app()` is stored in the `SagaSmithApp` instance but `SagaSmithApp` has no `on_unmount()` / `on_exit()` override to close it. With WAL mode the WAL file is not checkpointed on a clean quit; any crash leaves uncommitted data. The connection will be GC'd eventually, but there is no deterministic close. | Add `def on_unmount(self) -> None:` to `SagaSmithApp` that closes the connection stored on a service-connection attribute (e.g. `self._service_conn`), or pass the conn into the app and close it there. |
| high | `src/sagasmith/onboarding/store.py` | 54–69 | **`OnboardingStore.commit()` skips the RedactionCanary scan** — `PlayerProfile`, `ContentPolicy` (hard_limits, soft_limits, preferences), and `HouseRules` JSON are written directly to SQLite with no `RedactionCanary.scan()` call. `ContentPolicy.hard_limits` and `soft_limits` keys are free-form player strings; a player could enter a secret-shaped string (e.g. an API key copy-pasted into a hard-limit topic). Every other write path in this codebase (SettingsRepository.put, SafetyEventService._log, turn_close) runs the canary. This is an inconsistency in the trust boundary. | Add a `RedactionCanary` scan inside `commit()` before the `with self.conn:` block, mirroring the pattern in `SettingsRepository.put()`. Raise `TrustServiceError` on a hit. |
| high | `src/sagasmith/cli/configure_cmd.py` | 91–98 | **Uncaught `ValidationError` on invalid `--provider`** — the `--provider` option is an unvalidated `str`. If the user passes `--provider invalid`, line 91 constructs `ProviderSettings(provider=new_provider, ...)` which raises a Pydantic `ValidationError` that is not caught anywhere in `configure_command`. The exception escapes to Typer as an unhandled error rather than exiting with code 2. The same issue exists in `init_cmd.py` line 61 / `init_campaign`. | Wrap the `ProviderSettings(...)` constructor call (and the corresponding call in `init_campaign`) in `try/except pydantic.ValidationError as exc:` and call `typer.echo(f"error: invalid provider value: {exc}", err=True); raise typer.Exit(code=2)`. |
| high | `src/sagasmith/app/campaign.py` | 80–116 | **Orphaned directory on failed `init_campaign`** — `root.mkdir()` is called first (line 80), then `player_vault.mkdir()`, then `open_campaign_db`, then `apply_migrations`. If any step after `root.mkdir()` raises (e.g. migration failure, ProviderSettings validation error), the partially-created `root/` directory is left on disk. A subsequent `init_campaign` call with the same path hits `FileExistsError` with no indication that the directory is corrupt/partial, blocking the user from retrying without manual cleanup. | Add a `try/except BaseException` around the entire body after `root.mkdir()` and call `shutil.rmtree(root, ignore_errors=True)` in the except branch before re-raising. |
| medium | `src/sagasmith/persistence/migrations.py` | 24 | **`conn.executescript()` breaks the atomic migration assumption** — `sqlite3.executescript()` issues an implicit `COMMIT` before executing the script, so each migration SQL runs in its own auto-committed transaction. The `schema_version` row is then inserted separately and committed at line 31. If the process terminates between the `executescript` commit and the `schema_version` commit, the schema tables exist but `schema_version` records version 0, causing idempotent re-runs on next start. This is benign for `CREATE TABLE IF NOT EXISTS` migrations but will cause problems if a future migration is non-idempotent. | Document this limitation explicitly in the function docstring and add a note that all migration SQL files must be idempotent. Alternatively, read the SQL and execute it statement-by-statement inside an explicit `with conn:` block. |
| medium | `src/sagasmith/tui/widgets/narration.py` | 41–44 | **`NarrationArea.load_scrollback()` is dead code and inconsistent** — the method writes to `RichLog` but does NOT append to `self.logged_lines`. Meanwhile `SagaSmithApp.on_mount()` (app.py line 81–83) uses an `append_line()` loop for scrollback, so `load_scrollback()` is never called. If it were ever called, test assertions that rely on `logged_lines` would see incomplete state. | Remove `load_scrollback()` entirely (it is replaced by the `append_line()` loop in `on_mount`), or update it to also append to `self.logged_lines` for consistency. |
| medium | `src/sagasmith/onboarding/wizard.py` | 481–484 | **`_next_phase()` raises `IndexError` on `DONE`** — calling `_next_phase(OnboardingPhase.DONE)` (which is the last element in `PHASE_ORDER`) raises `IndexError: tuple index out of range`. This path is not reachable through the public `OnboardingWizard.step()` API because the DONE-guard fires first, and `REVIEW` is handled by `_handle_review_step`. However there is no internal guard in `_next_phase` itself, making it fragile against future refactors or direct calls. | Add an explicit guard: `if current == OnboardingPhase.DONE: raise RuntimeError("_next_phase called with DONE")`. |
| medium | `src/sagasmith/tui/widgets/narration.py` | 25 | **`logged_lines` initialised in `compose()` rather than `__init__`** — the `compose()` guard on line 37 (`if not hasattr(self, 'logged_lines')`) mitigates this, but it means the attribute is not established before composition, which is unusual for Textual widgets and hides the initialization contract. The `append_line` fallback path is only tested in pathological ordering. | Move `self.logged_lines: list[str] = []` into a `__init__` override or a `DEFAULT_CSS`-style class attribute so the field is always present before `compose()` runs. |
| medium | `src/sagasmith/app/config.py` | 32–54 | **`SettingsRepository.put()` does not commit** — the method calls `self.conn.execute(...)` without a `with self.conn:` wrapper, leaving commit responsibility entirely to the caller. All current callers do wrap in a transaction, but nothing enforces this; future callers could silently omit the commit and lose settings writes without error. | Wrap the `conn.execute` call in `with self.conn:` so `put()` is self-contained. The redundant `with conn:` in callers becomes a no-op (nested `with conn:` in sqlite3 is safe). |
| low | `src/sagasmith/tui/app.py` | 62 | **`self.commands = None` typed as `# type: ignore[assignment]`** — `commands` is set to `None` in `__init__` but later assigned a `CommandRegistry`. The type annotation is suppressed. In `on_command_invoked` (line 107) there is a `if self.commands is None:` guard but the attribute has no formal type annotation. | Annotate: `self.commands: CommandRegistry \| None = None` so the type checker can verify the guard at line 107. |
| low | `src/sagasmith/cli/play_cmd.py` | 56–62 | **`play_cmd._print_status_line` opens a read-only connection without WAL** — `open_campaign_db(paths.db, read_only=True)` on line 54 opens with `?mode=ro` URI. In WAL mode, readers can see committed data without acquiring a write lock; this is safe. However `PRAGMA journal_mode = WAL` at line 26 of `db.py` is a no-op on a read-only connection and will silently succeed returning the current journal mode. This is fine but worth documenting. | Add a comment in `open_campaign_db` noting that `journal_mode` and `synchronous` pragmas are silently ignored for `mode=ro` connections. |
| low | `src/sagasmith/onboarding/prompts.py` | 353–357 | **`_parse_single_choice` accepts empty string when `field.choices` contains `""`** — if `raw` is `None`, `str(None).strip()` produces `"none"` (not `""`); however if `raw = ""`, the choice `""` is valid if it happens to be in `field.choices`. No current field has `""` as a choice, but the implicit `str(None)` coercion to `"none"` (line 353) is unexpected; a cleaner path would be to treat `None` as a missing required field. | Replace `str(raw).strip() if raw is not None else ""` with an explicit `None` → required-field error path before the `choices` check, consistent with the other parsers. |

---

## Critical Issues

### CR-01: Service connection never closed (`runtime.py`)

**File:** `src/sagasmith/tui/runtime.py:48`

**Issue:** `service_conn` is opened in `build_app()` and stored implicitly via `OnboardingStore(conn=service_conn)` and `SafetyEventService(conn=service_conn)`. `SagaSmithApp` does not override `on_unmount()` or any exit hook. Python's GC will eventually close the connection, but:
- In WAL mode the WAL log is not checkpointed until a write connection closes cleanly.
- Any pending writes at TUI quit are subject to OS-level SQLite WAL recovery only.
- In test harness (`app.run_test()`), this leaks file handles within a test session.

**Fix:**
```python
# In SagaSmithApp.__init__, store the conn:
self._service_conn: sqlite3.Connection | None = None

# In build_app(), after opening:
service_conn = open_campaign_db(paths.db, read_only=False)
app._service_conn = service_conn   # owned by app for lifecycle
app.onboarding_store = OnboardingStore(conn=service_conn)
app.safety_events = SafetyEventService(conn=service_conn)

# In SagaSmithApp, add:
def on_unmount(self) -> None:
    if self._service_conn is not None:
        self._service_conn.close()
        self._service_conn = None
```

---

## High Issues

### HR-01: `OnboardingStore.commit()` bypasses RedactionCanary (`store.py`)

**File:** `src/sagasmith/onboarding/store.py:54`

**Issue:** Free-form player text in `ContentPolicy.hard_limits`, `soft_limits`, `preferences`, and `PlayerProfile` fields is written directly to SQLite without a `RedactionCanary.scan()`. Every other write path in the codebase that writes free-form text runs the canary. This breaks the consistent trust-boundary invariant.

**Fix:**
```python
from sagasmith.evals.redaction import RedactionCanary
from sagasmith.services.errors import TrustServiceError

def commit(self, campaign_id: str, triple: OnboardingTriple) -> None:
    canary = RedactionCanary()
    for label, payload in [
        ("player_profile", triple.player_profile.model_dump_json()),
        ("content_policy", triple.content_policy.model_dump_json()),
        ("house_rules", triple.house_rules.model_dump_json()),
    ]:
        hits = canary.scan(payload)
        if hits:
            raise TrustServiceError(
                f"onboarding commit rejected by redaction canary: "
                f"record={label} label={hits[0].label}"
            )
    now = datetime.now(UTC).isoformat()
    with self.conn:
        # ... existing INSERT OR REPLACE statements unchanged
```

### HR-02: Invalid `--provider` crashes with unhandled `ValidationError` (`configure_cmd.py`, `init_cmd.py`)

**File:** `src/sagasmith/cli/configure_cmd.py:91`

**Issue:** `ProviderSettings(provider=new_provider, ...)` raises `pydantic.ValidationError` when `new_provider` is not `"openrouter"` or `"fake"`. This is not caught; Typer propagates it as an unhandled Python exception rather than a clean exit-code-2.

**Fix:**
```python
import pydantic

try:
    updated = ProviderSettings(
        provider=new_provider,  # type: ignore[arg-type]
        ...
    )
except pydantic.ValidationError as exc:
    typer.echo(f"error: invalid settings value: {exc}", err=True)
    raise typer.Exit(code=2) from None
```
Apply the same pattern in `init_campaign()` or at the `init_cmd.py` call site.

### HR-03: Orphaned directory after failed `init_campaign` (`campaign.py`)

**File:** `src/sagasmith/app/campaign.py:80`

**Issue:** If anything raises after `root.mkdir()` (migration failure, DB error, `ProviderSettings` validation error), the partial `root/` directory is left on disk. The next `init_campaign` call with the same `root` hits `FileExistsError` with the message "Campaign already exists" — misleading, since the directory is incomplete.

**Fix:**
```python
import shutil

root.mkdir(parents=True, exist_ok=False)
try:
    (root / "player_vault").mkdir()
    conn = open_campaign_db(root / "campaign.sqlite")
    try:
        # ... rest of setup
    finally:
        conn.close()
    _write_toml(manifest, root / "campaign.toml")
    return manifest
except BaseException:
    shutil.rmtree(root, ignore_errors=True)
    raise
```

---

## Medium Issues

### MR-01: `executescript()` breaks migration atomicity (`migrations.py`)

**File:** `src/sagasmith/persistence/migrations.py:24`

**Issue:** `conn.executescript(sql)` issues an implicit `COMMIT` before executing, so each migration SQL file runs auto-committed before the `schema_version` row is inserted. A crash between the two leaves the schema modified but `schema_version` at the old value, causing re-execution on next start. All current migrations use `CREATE TABLE IF NOT EXISTS` so re-runs are safe, but this is a correctness latent bomb for any future non-idempotent migration.

**Fix:** Document the constraint in the function docstring and enforce a policy that all migration files must be written as idempotent SQL. Alternatively, parse and execute statements individually inside a `with conn:` block.

### MR-02: Dead `NarrationArea.load_scrollback()` method (`narration.py`)

**File:** `src/sagasmith/tui/widgets/narration.py:41`

**Issue:** `load_scrollback()` writes to `RichLog` but does not update `self.logged_lines`, and it is never called from `SagaSmithApp.on_mount()` (which uses `append_line()` instead). The method is dead code and its `logged_lines` inconsistency would break test assertions if it were ever called.

**Fix:** Remove `load_scrollback()` entirely.

### MR-03: `_next_phase()` IndexError on `DONE` with no guard (`wizard.py`)

**File:** `src/sagasmith/onboarding/wizard.py:484`

**Issue:** `PHASE_ORDER[idx + 1]` where `idx` is the last index raises `IndexError`. Not reachable today through `OnboardingWizard.step()`, but a future refactor could call it directly.

**Fix:**
```python
def _next_phase(current: OnboardingPhase) -> OnboardingPhase:
    if current == OnboardingPhase.DONE:
        raise RuntimeError("_next_phase called on terminal phase DONE")
    idx = PHASE_ORDER.index(current)
    return PHASE_ORDER[idx + 1]
```

### MR-04: `logged_lines` initialised in `compose()` not `__init__` (`narration.py`)

**File:** `src/sagasmith/tui/widgets/narration.py:25`

**Issue:** `self.logged_lines` is assigned in `compose()`. If `append_line()` is called before composition (possible in test setup sequences), the fallback `hasattr` guard kicks in. This works, but the contract is obscure. Using `__init__` is the standard pattern.

**Fix:**
```python
def __init__(self, *args: object, **kwargs: object) -> None:
    super().__init__(*args, **kwargs)  # type: ignore[arg-type]
    self.logged_lines: list[str] = []

def compose(self):  # type: ignore[override]
    yield RichLog(id="narration-log", wrap=True, highlight=False, markup=False, auto_scroll=True)
```
And remove the `if not hasattr` guard from `append_line`.

### MR-05: `SettingsRepository.put()` relies on caller to commit (`config.py`)

**File:** `src/sagasmith/app/config.py:44`

**Issue:** `self.conn.execute(...)` is called without `with self.conn:`, delegating commit responsibility to callers. All current callers correctly wrap with `with conn:`, but this is an implicit coupling that could silently lose writes if a future caller forgets the transaction wrapper.

**Fix:**
```python
def put(self, campaign_id: str, key: str, value: BaseModel) -> None:
    value_json = value.model_dump_json()
    hits = RedactionCanary().scan(value_json)
    if hits:
        raise TrustServiceError("settings write rejected: secret-shaped payload")
    updated_at = datetime.now(UTC).isoformat()
    with self.conn:
        self.conn.execute(
            """INSERT INTO settings ...""",
            (campaign_id, key, value_json, updated_at),
        )
```

---

## Low / Info Issues

### LW-01: `self.commands` lacks type annotation in `SagaSmithApp` (`app.py`)

**File:** `src/sagasmith/tui/app.py:62`

**Issue:** `self.commands = None  # type: ignore[assignment]` suppresses the type checker rather than providing a proper annotation. The `if self.commands is None:` guard at line 107 is not type-checked.

**Fix:** Annotate: `self.commands: CommandRegistry | None = None` and remove the `# type: ignore`.

### LW-02: Read-only `open_campaign_db` silently ignores pragma settings (`db.py`)

**File:** `src/sagasmith/persistence/db.py:26`

**Issue:** `PRAGMA journal_mode = WAL` and `PRAGMA synchronous = NORMAL` are no-ops on `mode=ro` connections. They succeed silently, which is correct behaviour, but can mislead readers into thinking WAL/sync settings are actively applied on read-only opens.

**Fix:** Add a comment: `# Note: journal_mode and synchronous pragmas are accepted but ignored by read-only (mode=ro) connections`.

### LW-03: `_parse_single_choice` coerces `None` to `"none"` string (`prompts.py`)

**File:** `src/sagasmith/onboarding/prompts.py:353`

**Issue:** `str(raw).strip() if raw is not None else ""` — if `raw is None`, the result is `""`, which is only valid if `""` is in `field.choices` (it never is). This means `None` on a required single-choice field correctly produces an error, but via the `value not in field.choices` check with a confusing error message ("'' must be one of ...") rather than "'field_id' is required".

**Fix:**
```python
def _parse_single_choice(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if raw is None:
        if field.required:
            return "", [f"'{field.id}' is required"]
        return "", []
    value = str(raw).strip()
    if value not in field.choices:
        choices_str = ", ".join(field.choices)
        return value, [f"'{field.id}' must be one of {{{choices_str}}}"]
    return value, []
```

---

## Summary

| Severity | Count | Blocking? |
|----------|-------|-----------|
| critical | 1 | **Yes** — service connection never closed; WAL checkpoint risk on quit |
| high | 3 | **Yes** — missing canary on onboarding write; uncaught ValidationError on bad --provider; orphaned directory on init failure |
| medium | 5 | No — code quality / latent correctness issues |
| low | 3 | No — style and minor improvements |
| **total** | **12** | |

**Blocking assessment:** The 1 critical and 3 high findings should be fixed before promotion. They represent a resource leak (CR-01), a gap in the project's core secret-redaction invariant (HR-01), and two user-visible correctness bugs (HR-02, HR-03). None are exploitable in isolation during MVP development with `provider=fake`, but they violate the "trust-before-breadth" engineering rule and will matter once `provider=openrouter` is in use.

---

_Reviewed: 2026-04-27T16:00:00Z_
_Reviewer: gsd-code-reviewer (anthropic/claude-sonnet-4.6)_
_Depth: standard_
