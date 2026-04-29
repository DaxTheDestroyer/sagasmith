---
phase: 07-memory-vault-and-resume
plan: 02
subsystem: persistence, memory, archivist
tags: [vault, turn-close, atomic-write, repair, sync]
dependency_graph:
  requires: [07-01]
  provides: [vault-page-upsert, turn-close-vault-integration, repair-signaling]
  affects: [07-03, 07-05]
tech_stack:
  added: []
  patterns: [atomic file operations, Pydantic v2 deterministic validation, slug collision resolution, vault-to-player sync with field stripping]
key_files:
  created:
    - src/sagasmith/agents/archivist/skills/vault-page-upsert/SKILL.md
    - src/sagasmith/agents/archivist/skills/vault-page-upsert/logic.py
    - src/sagasmith/persistence/migrations/0007_vault_sync_warning.sql
    - tests/archivist/test_vault_page_upsert.py
    - tests/persistence/test_turn_close_vault.py
  modified:
    - src/sagasmith/persistence/turn_close.py
    - src/sagasmith/persistence/repositories.py
    - src/sagasmith/schemas/persistence.py
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/agents/archivist/node.py
decisions:
  - "Vault page writes are performed after SQLite commit; any failure flips turn status to needs_vault_repair"
  - "Player-vault sync failures set a persistent warning but do not block turn completion"
  - "Slug collisions append _2, _3, … until a unique filename is found"
  - "Meta pages (world_bible, campaign_seed) use LoreFrontmatter with category marker and gm_only visibility"
  - "First-encountered session number taken from session_state.session_number; never overwritten on updates"
metrics:
  duration: ""
  completed_date: ""
  tasks_total: 4
  tasks_completed: 4
files_changed: 11
---

# Phase 07 Plan 02: Vault-Page-Upsert and Turn-Close Vault Integration

## One-Liner

Deterministic vault page upsert with atomic writes, slug collision resolution, and integrated turn-close persistence that orchestrates master vault writes, derived index refresh (deferred to 07-03), and player-vault sync with repair signaling.

## What Was Implemented

### 1. vault-page-upsert Skill

- **SKILL.md** — deterministic contract: create/update a master vault page with complete frontmatter.
- **logic.py** — receives `vault_service`, `entity_draft` (dict with name & type), `visibility`, `session_number`:
  - Derives slug using EntityResolver's `slugify`.
  - Determines target subfolder and prefix from entity type (NPC → `npcs/npc_<slug>.md`, etc.).
  - Handles slug collisions by trying `_2`, `_3`, … until a free filename is found.
  - Fills required type-specific fields with safe defaults (e.g., NPCs: species="unknown", role="unknown", status="alive", disposition_to_pc="neutral").
  - Validates frontmatter via Pydantic (`model_validate`); raises `ValueError` on failure — no file written.
  - Calls `vault_service.write_page(...)`, then refreshes the resolver.
  - Returns `(written_path, "created")` or `(written_path, "updated")`.
  - Update path: when `entity_draft` includes explicit `id` and the file already exists, merge fields but preserve original `first_encountered`.

### 2. Turn-Close-Persistence Extended

**TurnCloseBundle** (`persistence/turn_close.py`) extended with:
- `vault_pages: list[VaultPage]` — pages to write post-commit.
- `rolling_summary: str | None` — optional summary to meta page.

**close_turn** now:
1. Executes SQLite transaction (steps 1–8) inside a try block. On error: rollback and raise `TrustServiceError`.
2. After successful commit, if `vault_service` provided and `vault_pages` non-empty:
   - Atomically writes each page to master vault (using `vault_service.write_page`).
   - On any write exception: updates just-committed `TurnRecord` to `"needs_vault_repair"` and re-raises.
   - Refreshes `vault_service.resolver`.
3. Derived indices update deferred to Plan 07-03 (no-op).
4. Calls `vault_service.sync()`:
   - On exception, catches and writes `sync_warning` message to `turn_records.sync_warning` column; status remains `"complete"`.

**Schema changes:**
- `TurnRecord` (`schemas/persistence.py`) gains `sync_warning: str | None`.
- `TurnRecordRepository.upsert` and `get` updated to handle new column.

**Migration:** `0007_vault_sync_warning.sql` adds `sync_warning TEXT` to `turn_records`.

### 3. Runtime Integration

**GraphRuntime.resume_and_close** (`graph/runtime.py`):
- Accepts `vault_pages` and `rolling_summary` optional parameters.
- Pulls `vault_pending_writes` from final graph state (produced by archivist) and builds it into the `TurnCloseBundle`.
- Pulls in `rolling_summary` from state and includes it.
- Passes `vault_service` (from `bootstrap.services`) into `close_turn`.

### 4. Archivist Node Enhancements

`archivist_node` (`agents/archivist/node.py`) now:

- Activates new `vault-page-upsert` skill alongside existing ones.
- Increments `turn_count`; reads `session_number`.
- **Meta page persistence (first turn):** If `session_state.turn_count == 1` and state contains `world_bible` or `campaign_seed`, creates Lore pages under `meta/` with category markers and `gm_only` visibility; appends to `vault_pending_writes`.
- **Entity page creation:** Iterates `scene_brief.present_entities`. For each name:
  - Attempts resolution via `vault_service.resolver.resolve`. If not found, builds a minimal NPC draft (type=npc, species/role/status/disposition defaults) with visibility=`player_known` (present entities are known).
  - Calls `vault_page_upsert` and appends resulting page to `vault_pending_writes`.
- **Rolling summary:** If state contains `rolling_summary` string, creates a Lore meta page (category=rolling_summary) and appends.
- Returns state dict including `"vault_pending_writes": list[VaultPage]`.

### 5. Tests

**tests/archivist/test_vault_page_upsert.py** (5 tests):
- Creates NPC page, verifies file, frontmatter.
- Slug collision appends `_2`, `_3`.
- Invalid draft (missing name/type) raises; no file remains.
- Update existing page by explicit `id` merges fields and preserves `first_encountered`.
- Location page creation works.

**tests/persistence/test_turn_close_vault.py** (4 tests):
- Successful vault writes + derived indices + player vault sync (gm_only stripped, player_known copied).
- Vault write failure → turn status `needs_vault_repair`.
- Sync failure → `sync_warning` set, status remains `complete`.
- No-op when `vault_service` is None.

**Updated existing migration tests** (`test_migrations.py`, `test_campaign_settings_schema.py`) to include v7 migration and schema_version 7.

## Verification

All automated tests pass:

```
pytest tests/archivist/test_vault_page_upsert.py -x   # 5 passed
pytest tests/persistence/test_turn_close_vault.py -x # 4 passed
pytest tests/persistence/test_migrations.py -x       # 8 passed (updated)
pytest tests/persistence/test_campaign_settings_schema.py -x # 2 passed (updated)
pytest tests/persistence/test_turn_close.py -x       # 6 passed (unchanged)
pytest tests/vault/ tests/archivist/ tests/persistence/ -x  # 41 passed
```

Lint (`ruff check`) reports no errors on modified files after auto-fix. Typecheck (`pyright`) runs clean aside from pre-existing dynamic-state warnings (acceptable).

## Deviations from Plan

- **Task 1 slug prefix:** The vault-page-upsert initially omitted type prefix in filename; corrected by adding prefixed filenames using mapping consistent with VAULT_SCHEMA.
- **Plan listed file** `src/sagasmith/agents/archivist/skills/turn-close-persistence/logic.py` does not exist; we implemented the required functionality in `persistence/turn_close.py` instead (as per specification §4).
- **sync WARNING column** added as a new field to `TurnRecord` and repositories updated accordingly.
- **Entity type inference** in archivist_node defaults to `"npc"` for present_entities (first slice simplification). Rich type inference delegated to future plans.

## Stubs / Known Gaps

- Entity type resolution beyond NPCs is rudimentary (hard-coded to npc). Future plans will provide richer type inference from scene context.
- Derived index updates (FTS5, NetworkX) are not yet implemented (deferred to Plan 07-03).
- Player-vault `index.md` and `log.md` regeneration not implemented (Plan 07-05).
- The `vault_service.sync()` currently copies pages but does not strip `<!-- gm:` comments (stripping only GM-named fields, not body comments). This will be enhanced later.

## Auth Gates

None.
