---
phase: 07-memory-vault-and-resume
plan: 03
type: summary
wave: 3
status: complete
---

# 07-03 Summary: Derived Indices (FTS5 + NetworkX)

## Objective

Replace the Phase 6 memory-packet stub with full retrieval using FTS5 full-text search and NetworkX graph neighborhoods. The memory packet becomes a hybrid context engine that respects the token cap while pulling exact, semantic, and relational knowledge from the vault.

## What Was Done

### 1. FTS5 Full-Text Search Index (`src/sagasmith/memory/fts5.py`)
- `FTS5Index` class backed by SQLite FTS5 virtual table
- `index_page()` — incremental upsert of individual vault pages
- `remove_page()` — delete from index
- `rebuild_all()` — full scan of vault directory, skips `gm_only` pages, strips frontmatter before indexing body
- `query()` — keyword search returning `(vault_path, rank)` tuples
- Helper functions: `get_fts5_index()`, `_extract_body()`, `_extract_visibility()`

### 2. NetworkX Graph Loader (`src/sagasmith/memory/graph.py`)
- `VaultGraph` class wrapping a `nx.DiGraph`
- `load_from_vault()` — scans vault markdown, builds nodes and edges from:
  - Wikilinks `[[page_id]]` in body text
  - Frontmatter relationships: `connects_to`, `known_members`, `related_entities`, `callbacks`, `related_quest`, `held_by`, `given_by`, `factions`, `location_current`
- `get_neighbors()` — BFS traversal (both directions) up to N hops
- `get_neighbors_by_type()` — type-filtered neighbor query
- Module-level singleton cache: `get_vault_graph()`, `warm_vault_graph()`, `reset_vault_graph_cache()`
- **Bug fixed:** BFS was not adding the final frontier to visited set

### 3. Hybrid Memory Packet Assembly (`src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py`)
- Replaced `assemble_memory_packet_stub` with full `assemble_memory_packet` function
- **Retrieval pipeline:**
  1. Rolling summary from `state["rolling_summary"]` (or fallback generation)
  2. Entity resolution via vault `EntityResolver` → `MemoryEntityRef` with vault_path
  3. FTS5 keyword search for scene-relevant vault pages
  4. NetworkX 1-hop graph neighbor retrieval (up to 10 neighbors)
  5. Open callback discovery from vault (`status=open`, `seeded_in ≤ current_session`)
  6. Recent transcript from SQLite (last 8 entries)
  7. Token cap enforcement with truncation priority: oldest recent_turns first, then summary tail
- `assemble_memory_packet_stub` preserved for backward compatibility
- Hyphen-named skill directory (`memory-packet-assembly/logic.py`) re-exports from underscore variant

### 4. Turn-Close Integration (`src/sagasmith/persistence/turn_close.py`)
- `_update_derived_indices(conn, vault_service, pages)` called after vault writes
- FTS5 incremental index update for each written page
- NetworkX graph cache incremental update (node + edges added for new pages)
- Non-fatal: failures in derived indices don't block turn completion

### 5. TUI Runtime Warm-Start (`src/sagasmith/tui/runtime.py`)
- `warm_vault_graph(vault_service.master_path)` called during app startup
- Graph cache is pre-populated before first turn

### 6. Archivist Node Update (`src/sagasmith/agents/archivist/node.py`)
- Uses `assemble_memory_packet()` with vault_service when available
- Falls back to stub behavior when vault_service is None

### 7. Orator Node Update (`src/sagasmith/agents/orator/node.py`)
- Uses `assemble_memory_packet()` with vault_service from services bundle

## Files Modified

| File | Change |
|------|--------|
| `src/sagasmith/memory/__init__.py` | Added exports for FTS5Index, VaultGraph, cache helpers |
| `src/sagasmith/memory/fts5.py` | **NEW** — FTS5 full-text search index |
| `src/sagasmith/memory/graph.py` | **NEW** — NetworkX graph loader and neighbor query |
| `src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py` | Full hybrid retrieval implementation |
| `src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py` | Re-export wrapper for import compatibility |
| `src/sagasmith/agents/archivist/skills/memory-packet-assembly/SKILL.md` | Updated for Phase 7 hybrid retrieval |
| `src/sagasmith/agents/archivist/node.py` | Uses full `assemble_memory_packet` with vault_service |
| `src/sagasmith/agents/orator/node.py` | Uses full `assemble_memory_packet` with vault_service |
| `src/sagasmith/persistence/turn_close.py` | Added `_update_derived_indices()` for FTS5 + NetworkX |
| `src/sagasmith/tui/runtime.py` | Added `warm_vault_graph()` on startup |
| `pyproject.toml` | Added `networkx>=3,<4` dependency |

## Tests Created

| File | Tests | Status |
|------|-------|--------|
| `tests/memory/test_fts5.py` | 18 tests: index create, query, upsert, remove, rebuild, visibility filtering | ✅ All pass |
| `tests/memory/test_graph_retrieval.py` | 17 tests: load, wikilinks, connects_to, factions, quests, callbacks, items, NPCs, neighbors, depth, cache | ✅ All pass |
| `tests/agents/archivist/test_memory_packet_full.py` | 14 tests: hybrid assembly, entity resolution, FTS5, graph neighbors, callbacks, token cap, backward compat | ✅ All pass |

**Total: 49 new tests, all passing.**

## Tests Updated (pre-existing fixture issues from Wave 1)

| File | Fix |
|------|-----|
| `src/sagasmith/evals/fixtures.py` | Added `vault_master_path`, `vault_player_path`, `rolling_summary` to `make_valid_saga_state` |
| `tests/fixtures/valid_saga_state.json` | Added vault fields |
| `tests/schemas/test_validation_gate.py` | Added vault fields to `make_saga_state` |
| `tests/graph/test_checkpoints.py` | Added vault fields to `_play_state` |
| `tests/integration/test_narration_recovery.py` | Added vault fields to `_play_state` |
| `tests/agents/test_nodes_with_skills.py` | Updated archivist skill assertion for multi-skill activation |
| `tests/agents/archivist/test_memory_packet_stub.py` | Updated retrieval_notes assertions for new format |
| `tests/skills_adapter/test_production_catalog.py` | Added `entity-resolution` to expected surfaces |

## Additional Fixes (pre-existing)

- `src/sagasmith/agents/archivist/skills/entity-resolution/SKILL.md` — Fixed `implementation_surface: pure` → `deterministic`

## Success Criteria Verification

- [x] **VAULT-07:** MemoryPacket assembly pulls from FTS5, NetworkX graph neighbors, callbacks, summary, and recent turns (5 sources)
- [x] **AI-11:** MemoryPacket enforces token_cap via `estimate_tokens`; truncation drops oldest turns first, then summary tail
- [x] **PERS-06:** `rebuild_all()` and `load_from_vault()` can reconstruct FTS5 and graph from master vault alone

## Known Issues

- **Python 3.14 compatibility:** Several pre-existing tests fail due to Python 3.14 not meeting `<3.14` requirement and `cursor.lastrowid` behavior changes. Not caused by Wave 3.
- **LanceDB:** Deferred per D-01; no-op stub. Post-MVP activation requires no changes to the retrieval pipeline.
