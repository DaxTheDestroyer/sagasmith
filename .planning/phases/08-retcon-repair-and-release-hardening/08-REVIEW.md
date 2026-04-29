---
phase: 08-retcon-repair-and-release-hardening
reviewed: 2026-04-29T17:46:19Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - Makefile
  - src/sagasmith/agents/archivist/transcript_context.py
  - src/sagasmith/cli/smoke_cmd.py
  - src/sagasmith/evals/harness.py
  - src/sagasmith/graph/runtime.py
  - src/sagasmith/persistence/migrations/0008_retcon_audit.sql
  - src/sagasmith/persistence/repositories.py
  - src/sagasmith/persistence/retcon.py
  - src/sagasmith/persistence/turn_close.py
  - src/sagasmith/schemas/export.py
  - src/sagasmith/schemas/persistence.py
  - src/sagasmith/tui/app.py
  - src/sagasmith/tui/commands/control.py
  - tests/agents/archivist/test_transcript_context.py
  - tests/evals/test_mvp_smoke.py
  - tests/evals/test_smoke_cli.py
  - tests/integration/test_retcon_runtime.py
  - tests/persistence/test_campaign_settings_schema.py
  - tests/persistence/test_migrations.py
  - tests/persistence/test_retcon_repositories.py
  - tests/persistence/test_turn_close_vault.py
  - tests/tui/test_commands_post_interrupts.py
  - tests/tui/test_control_commands.py
  - tests/tui/test_retcon_command.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-04-29T17:46:19Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Reviewed 24 files across the Phase 8 retcon/repair/release-hardening plan implementations. The codebase is well-structured with clear separation between persistence, service, runtime, and TUI layers. The retcon feature is designed with audit retention, deterministic preview, typed confirmation tokens, and safe canonical exclusion — all of which are correctly implemented. No critical security vulnerabilities were found. Two warnings and three informational items were identified, mostly around SQL injection hardening, missing post-retcon vault warning sync, and transaction pattern consistency.

The MVP smoke harness and release gate are correctly scoped to deterministic, provider-free paths. The Makefile targets compose existing quality gates appropriately. Test coverage is comprehensive with 40+ tests across persistence, integration, and TUI layers.

## Warnings

### WR-01: SQL table name string interpolation creates injection surface

**File:** `src/sagasmith/persistence/retcon.py:209`
**Issue:** The `_count_rows_for_turns` helper interpolates the `table` parameter directly into a SQL string via f-string:
```python
f"SELECT COUNT(*) FROM {table} WHERE turn_id IN ({placeholders})"
```
While current callers pass only the hardcoded strings `"transcript_entries"` and `"roll_logs"`, the function signature accepts an arbitrary `str` table name. If this helper is ever reused with user-controlled or externally-derived table names, it becomes a SQL injection vector. The pattern is a latent injection surface where a future refactor could unknowingly introduce a vulnerability.

**Fix:** Add a whitelist guard or use a safe lookup:
```python
_ALLOWED_COUNT_TABLES = frozenset({"transcript_entries", "roll_logs"})

def _count_rows_for_turns(conn: sqlite3.Connection, table: str, turn_ids: list[str]) -> int:
    if table not in _ALLOWED_COUNT_TABLES:
        raise ValueError(f"Table {table} is not whitelisted for count queries")
    if not turn_ids:
        return 0
    placeholders = ", ".join("?" for _ in turn_ids)
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE turn_id IN ({placeholders})",
        tuple(turn_ids),
    ).fetchone()
    return int(row[0]) if row is not None else 0
```

---

### WR-02: Vault sync warning not refreshed after retcon

**File:** `src/sagasmith/tui/commands/control.py:187`
**Issue:** After a successful retcon confirmation, `app.sync_after_retcon()` is called to resync narration and mechanics. However, the vault sync warning — surfaced by `_sync_vault_warning_from_latest_turn()` — is never refreshed. After retcon marks turns as `retconned` (which changes the SQL-based "latest completed turn" query result), the displayed vault sync warning may be stale, potentially hiding a real sync issue from the player.

**Fix:** After `app.sync_after_retcon()`, also refresh the vault warning:
```python
app.sync_after_retcon()
with suppress(Exception):
    app._sync_vault_warning_from_latest_turn()
```

---

## Info

### IN-01: Overly broad `suppress(Exception)` swallows interrupt signals

**File:** `src/sagasmith/tui/app.py:348-351`
**Issue:** The `sync_after_retcon()` method wraps both sync calls in `suppress(Exception)`, which catches ALL `Exception` subclasses including `asyncio.CancelledError` (Python 3.9+) and other infrastructure exceptions. While the intent is to prevent transient TUI sync failures from crashing the app after a retcon, `suppress(Exception)` is overly broad. For example, a `KeyboardInterrupt` (which extends `BaseException`, not `Exception`) would NOT be suppressed, but `CancelledError` would — creating a possible hang scenario.

**Fix:** Narrow the suppression to the expected transient failure types:
```python
def sync_after_retcon(self) -> None:
    from contextlib import suppress

    with suppress(ValueError, TypeError, sqlite3.Error, RuntimeError):
        self._sync_narration_from_graph()
    with suppress(ValueError, TypeError, sqlite3.Error, RuntimeError):
        self._sync_mechanics_from_graph()
```
Alternatively, if the project prefers defensive suppression, document the rationale explicitly and add a `# noqa` justification.

---

### IN-02: Inconsistent service access pattern in RetconCommand

**File:** `src/sagasmith/tui/commands/control.py:164-169` vs `src/sagasmith/tui/commands/control.py:181,194`
**Issue:** The `RetconCommand.handle()` method uses two different paths to access retcon functionality:
- **Candidate listing (no-arg):** Creates `RetconService` directly using `app.graph_runtime.db_conn` (line 165)
- **Preview and confirm:** Delegates to `app.graph_runtime.preview_retcon()` and `app.graph_runtime.confirm_retcon()` (lines 181, 194)

The `graph_runtime` wrappers add checkpoint rewind and derived-layer rebuild orchestration (FTS5, NetworkX, player vault sync), but the candidate-listing path bypasses the runtime entirely. If the runtime ever needs to filter candidates or add runtime-level context, the no-arg path will miss it. This inconsistency could lead to divergent behavior in future iterations.

**Fix:** Add a `list_retcon_candidates` method to `GraphRuntime` and route all retcon operations through the runtime for consistency:
```python
# In GraphRuntime
def list_retcon_candidates(self, *, limit: int = 5):
    from sagasmith.persistence.retcon import RetconService
    return RetconService(self.db_conn, campaign_id=self.campaign_id).list_candidates(limit=limit)

# In RetconCommand.handle()
if not args:
    candidates = app.graph_runtime.list_retcon_candidates()
    ...
```

---

### IN-03: Explicit BEGIN transaction pattern differs from codebase convention

**File:** `src/sagasmith/persistence/retcon.py:136-155`
**Issue:** The `RetconService.confirm()` method uses an explicit `self.conn.execute("BEGIN")` + `try/except/else: commit/rollback` pattern. The project's [02-06] decision explicitly replaced explicit `BEGIN` in `close_turn` with SQLite's implicit transaction semantics to avoid "cannot start a transaction within a transaction" errors. While `confirm()` is not called from within an existing transaction in current call sites, using explicit `BEGIN` is inconsistent with the codebase convention and creates the same risk if a future caller wraps the confirm call inside a broader transaction.

**Fix:** Remove the explicit `BEGIN`/`COMMIT`/`ROLLBACK` wrapping and rely on SQLite's implicit transactions. Since `confirm` commits before the runtime's `_rewind_to_checkpoint` (which is the current design), the implicit commit-on-write behavior is sufficient:
```python
def confirm(self, selected_turn_id: str, confirmation_token: str, *, reason: str = "player_retcon") -> RetconResult:
    preview = self.preview(selected_turn_id)
    if confirmation_token != preview.confirmation_token:
        raise RetconBlockedError(...)
    audit_id = f"retcon-{uuid.uuid4().hex}"
    now = datetime.now(UTC).isoformat()
    TurnRecordRepository(self.conn).mark_retconned(preview.affected_turn_ids)
    RetconAuditRepository(self.conn).append(
        RetconAuditRecord(
            retcon_id=audit_id,
            campaign_id=self.campaign_id,
            selected_turn_id=selected_turn_id,
            affected_turn_ids=preview.affected_turn_ids,
            prior_checkpoint_id=preview.prior_checkpoint_id,
            confirmation_token=confirmation_token,
            reason=reason,
            created_at=now,
        )
    )
    # Implicit commit handled by caller or connection autocommit
    return RetconResult(...)
```
If explicit transaction boundaries are needed for atomicity, add a comment documenting why this method is an intentional exception to the [02-06] decision.

---

_Reviewed: 2026-04-29T17:46:19Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
