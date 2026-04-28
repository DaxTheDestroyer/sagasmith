# Phase 7: Memory, Vault, and Resume Differentiator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 07-memory-vault-and-resume
**Areas discussed:** LanceDB scope, Archivist skill subset, Entity creation trigger, /recap quality level

---

## LanceDB Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Stub interface, no embedding calls | LanceDB wired but no-op; FTS5 + NetworkX carry retrieval | ✓ |
| Active but opt-in | Fully implemented, disabled by default behind a campaign config flag | |
| Fully active from day one | Every vault page upsert embeds and upserts; adds per-turn embedding cost | |

**User's choice:** Stub interface, no embedding calls
**Notes:** Entity resolution uses slug + alias only. LanceDB activates post-MVP when per-turn embedding cost is confirmed acceptable.

---

## Archivist Skill Subset

| Option | Description | Selected |
|--------|-------------|----------|
| Core 8 + stub canon-conflict | vault-page-upsert, player-vault-sync, turn-close-persistence, memory-packet-assembly, entity-resolution, visibility-promotion, rolling-summary-update, session-page-authoring; canon-conflict stub | ✓ |
| Minimum viable (6 skills) | Write path only; defer rolling-summary-update, session-page-authoring, callback-reachability, canon-conflict, unlock | |
| Full catalog minus unlock (10 skills) | All 11 except master-vault-unlock including full canon-conflict LLM classifier and callback-reachability-query | |

**User's choice:** Core 8 + stub canon-conflict
**Notes:** callback-reachability-query and master-vault-unlock deferred. canon-conflict-detection logs a warning only (no classified CanonConflict event).

---

## Entity Creation Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Oracle declares, Archivist writes | Oracle adds typed entity drafts to SceneBrief; Archivist resolves + writes on turn-close | ✓ |
| Archivist extracts from narration | Lightweight LLM call post-narration to extract entity mentions | |
| Hybrid: Oracle declares known, Archivist flags unknown | Oracle declares planned entities; Archivist logs unresolved mentions | |

**User's choice:** Oracle declares, Archivist writes
**Notes:** Reuses existing inline-npc-creation skill from Phase 6. No extra LLM extraction cost. Deterministic and auditable.

---

## /recap Quality Level

| Option | Description | Selected |
|--------|-------------|----------|
| Read rolling summary + last N turns | Reads rolling-summary-update output + last 3–5 transcript rows; zero cost at recall time | ✓ |
| On-demand LLM recap generation | cheap_model call with rolling summary + transcript; better narrative quality per call | |
| Deterministic transcript formatter | Format session pages + transcript rows; no LLM; reads like a log | |

**User's choice:** Read rolling summary + last N turns
**Notes:** rolling-summary-update runs at scene boundaries (not per-turn), so cost is amortized. /recap is instant and zero-cost for the player.

---

## the agent's Discretion

- NetworkX graph load strategy (eager vs. lazy)
- FTS5 index update timing (per-upsert vs. batched)
- Rolling summary length cap
- Session-page-authoring LLM prompt template
- Visibility-promotion heuristics per entity type

## Deferred Ideas

- LanceDB semantic search — post-MVP
- callback-reachability-query — Phase 8 or post-MVP
- master-vault-unlock — post-MVP
- Full canon-conflict-detection LLM classifier — Phase 8 or post-MVP
- LLM entity extraction from narration — not chosen; Oracle-declare used instead
- /note in-game command — WISHLIST.md
