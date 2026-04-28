# Phase 7: Memory, Vault, and Resume Differentiator - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the full Archivist layer: atomic vault writes, two-vault spoiler-safe sync, entity resolution
(slug + alias), memory retrieval (FTS5 + NetworkX), `/recap`, quit/resume persistence, and vault
repair CLI commands. Phase 7 makes durable campaign memory the player-facing differentiator.

**Not in Phase 7 scope:** LanceDB semantic search (stubbed interface only), `master-vault-unlock`,
retcon confirmation/rollback (Phase 8), LLM-based entity extraction from narration, full
`canon-conflict-detection` (logged warning stub only), `callback-reachability-query`.

</domain>

<decisions>
## Implementation Decisions

### LanceDB / Semantic Search
- **D-01:** LanceDB is stubbed behind an interface — embed-and-upsert path is a no-op in Phase 7.
  Entity resolution uses slug + alias only (`VAULT_SCHEMA.md` §8 steps 1 and 2). MemoryPacket
  assembly uses SQLite FTS5 + NetworkX. The LanceDB interface is present in code but inactive;
  it activates post-MVP when per-turn embedding cost is confirmed acceptable.

### Archivist Skill Subset
- **D-02:** Eight skills ship as real code in Phase 7: `vault-page-upsert`, `player-vault-sync`,
  `turn-close-persistence`, `memory-packet-assembly` (FTS5 + NetworkX only), `entity-resolution`
  (slug + alias), `visibility-promotion`, `rolling-summary-update`, `session-page-authoring`.
- **D-03:** `canon-conflict-detection` ships as a stub — logs a structured warning rather than
  emitting a classified `CanonConflict` event. The schema already exists (STATE_SCHEMA.md); the
  LLM classifier is deferred to Phase 8 or post-MVP.
- **D-04:** `callback-reachability-query` and `master-vault-unlock` are deferred. Callbacks are
  seeded and tracked as vault pages (visibility: gm_only) but reachability scoring is not queried
  in Phase 7.

### Entity Creation Trigger
- **D-05:** Oracle declares new entities as typed drafts in SceneBrief using the existing
  `inline-npc-creation` skill (Phase 6). Archivist reads declared entities on turn-close, runs
  entity-resolution (slug + alias match), then calls vault-page-upsert. Deterministic, auditable,
  no additional LLM cost. Archivist never autonomously extracts entities from narration text in
  Phase 7.
- **D-06:** Oracle populates at minimum: type, name, aliases, visibility (default `gm_only`), and
  any specified disposition/role/status fields. Archivist completes remaining required frontmatter
  fields per `VAULT_SCHEMA.md` page schemas before writing.

### /recap Command
- **D-07:** `/recap` reads the rolling summary maintained by `rolling-summary-update` (updated at
  scene boundaries) plus the last 3–5 transcript rows from SQLite. Zero additional LLM cost at
  recap time. The rolling summary is the LLM-generated artifact; `/recap` only reads and formats.
- **D-08:** `rolling-summary-update` runs at scene close events (when Oracle replans or all beats
  resolve), not per-turn. Keeps summary cost bounded.

### WorldBible and CampaignSeed Vault Persistence (from Phase 6 D-11 deferral)
- **D-09:** Phase 6 stored WorldBible and CampaignSeed in graph state only. Phase 7 writes them to
  `meta/world_bible.md` and `meta/campaign_seed.md` in the master vault as a one-time write on the
  Archivist's first turn-close after campaign start (when `world_bible` field is present in state
  but no vault page exists yet). These `meta/` files are never projected to the player vault.

### Quit/Resume (TUI-08)
- **D-10:** Quit path: TUI sends session-end signal → Archivist completes turn-close-persistence
  (if turn is in progress) → player-vault-sync runs → TUI exits. If a turn is incomplete
  (pre-narration checkpoint only), the user is offered retry/discard before quit (reusing Phase 6
  narration recovery flow). On resume, the existing GRAPH-05 checkpoint resume path handles
  re-entry; Phase 7 ensures rolling summary and memory packet are loaded correctly on the first
  turn after resume.
- **D-11:** Player-vault sync runs on every turn-close after turn-close-persistence succeeds
  (PERSISTENCE_SPEC.md §4 Step 10). Sync failures surface a repair warning in the TUI status bar;
  the turn remains marked complete.

### the agent's Discretion
- NetworkX graph load strategy: eager on startup vs. lazy on first query
- FTS5 index update timing: per vault-page-upsert vs. batched at turn-close
- Exact rolling summary length cap (token budget within MemoryPacket cap)
- Session-page-authoring LLM prompt template and beat extraction heuristic
- Visibility-promotion heuristics for specific entity types

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning Scope
- `.planning/ROADMAP.md` — Phase 7 goal, requirements (CLI-04, PERS-03/05/06, VAULT-01–10,
  AI-11, TUI-08, QA-06), and success criteria.
- `.planning/REQUIREMENTS.md` — Full text of all Phase 7 requirement IDs.
- `.planning/PROJECT.md` — Trust-before-breadth principle, two-vault architecture motivation,
  vault-as-source-of-truth constraint.

### Vault and Persistence Specs
- `docs/specs/VAULT_SCHEMA.md` — Page type schemas (§5), filename/slug conventions (§4),
  visibility states (§6), GM-only stripping rules (§7), entity resolution algorithm (§8),
  derived read layers (§9), two-vault sync contract (§2.3), `index.md` / `log.md` spec (§5.8/5.9).
- `docs/specs/PERSISTENCE_SPEC.md` — Write ordering (§4), atomic vault writes (§6),
  checkpoint rules (§5), rebuild commands (§7).
- `docs/specs/GAME_SPEC.md` §3.5 — ArchivistAgent behavior contract: entity resolution, canon
  guarding, vault write ownership boundaries.

### Agent Skills Catalog
- `docs/specs/agents/archivist-skills.md` — All 11 Archivist skill definitions. Phase 7 ships:
  §2.1 (memory-packet-assembly), §2.3 (entity-resolution), §2.4 (vault-page-upsert),
  §2.5 (visibility-promotion), §2.6 (canon-conflict-detection, stub), §2.7 (turn-close-persistence),
  §2.8 (rolling-summary-update), §2.9 (session-page-authoring), §2.10 (player-vault-sync).
  Deferred: §2.2 (callback-reachability-query), §2.11 (master-vault-unlock).

### Prior Phase Context
- `.planning/phases/06-ai-gm-story-loop/06-CONTEXT.md` — D-11 (WorldBible/CampaignSeed deferred
  to Phase 7), D-15 (memory-packet-assembly stub that Phase 7 replaces), D-07 through D-09
  (Oracle re-plan triggers that define scene boundaries for rolling-summary-update).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sagasmith/agents/archivist/node.py` — Phase 7 replacement target; stub comment at top
  explicitly marks "Phase 7 replaces with full turn-close-persistence + vault upsert."
- `src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py` — Phase 6 stub using
  last 3 transcript rows; Phase 7 replaces with FTS5 + NetworkX + rolling summary retrieval.
- `src/sagasmith/agents/archivist/transcript_context.py` — SQLite transcript reader (last N rows);
  Phase 7 keeps this as the transcript tier of MemoryPacket assembly.
- `src/sagasmith/agents/archivist/entity_stubs.py` — entity stub helpers; Phase 7 extends into
  full entity-resolution (slug + alias matching against vault frontmatter).
- `src/sagasmith/graph/runtime.py` — `resume_and_close()`, pre-narration checkpoint detection;
  TUI-08 quit/resume logic extends here.
- `src/sagasmith/schemas/narrative.py` — `SceneBrief` (with `present_entities`), `MemoryPacket`;
  Phase 7 populates MemoryPacket from real FTS5 + NetworkX retrieval instead of stub.
- `src/sagasmith/providers/client.py` — `invoke_with_retry` for `rolling-summary-update` and
  `session-page-authoring` LLM calls.

### Established Patterns
- Atomic file replacement: write to temp → `os.replace()` → re-read and validate YAML frontmatter
  (PERSISTENCE_SPEC.md §6). All vault writes use this pattern without exception.
- `SchemaModel` with `extra="forbid"` for all boundary schemas.
- `DeterministicFakeClient` for all no-paid-call test paths.
- Agent nodes return dict state updates only; vault writes happen in turn-close, not inside nodes.
- ContextVar handoff: nodes call `get_current_activation().set_skill(...)` when activation is
  present.

### Integration Points
- `src/sagasmith/agents/archivist/node.py` — Phase 7 replaces with full turn-close-persistence
  + vault-page-upsert; returns updated vault path state fields.
- `src/sagasmith/graph/graph.py` — may need new `SagaGraphState` fields: `vault_master_path`,
  `vault_player_path`, `rolling_summary`, `session_number`.
- TUI command registry (Phase 3 command stubs) — `/recap` stub exists; Phase 7 wires to
  rolling-summary-update output + transcript reader.
- CLI entry point — `ttrpg vault rebuild` and `ttrpg vault sync` commands added for CLI-04.
- SQLite schema — migration for Phase 7 additions: vault path tracking, session number,
  rolling summary blob storage.

</code_context>

<specifics>
## Specific Ideas

- The two-vault model is the player-facing differentiator — the Obsidian-compatible player vault
  is what sets SagaSmith apart. Prioritize player vault correctness (zero GM leakage, valid YAML,
  all wikilinks resolving) above derived index completeness.
- LanceDB is an upgrade path, not a Phase 7 blocker. The stub interface keeps Phase 8 or post-MVP
  activation surgery-free.
- Rolling summary maintained proactively at scene boundaries means `/recap` is instant and
  zero-cost — good for player experience.
- Oracle already has `inline-npc-creation` from Phase 6; Phase 7 just reads what Oracle declares
  rather than adding a second entity-extraction LLM call.

</specifics>

<deferred>
## Deferred Ideas

- LanceDB semantic search — activate post-MVP when per-turn embedding cost is confirmed acceptable.
- `callback-reachability-query` — NetworkX + open callbacks; deferred to Phase 8 or post-MVP.
- `master-vault-unlock` — post-campaign director's-cut vault; post-MVP.
- Full `canon-conflict-detection` LLM classifier — Phase 7 logs warning stub; Phase 8 or post-MVP
  for classified `CanonConflict` events.
- LLM-based entity extraction from narration text — Oracle-declare approach chosen instead.
- Real-time token-by-token streaming to TUI — carried from Phase 6 deferral.
- `/note` in-game canon annotation command — WISHLIST.md, post-MVP.

</deferred>

---

*Phase: 07-memory-vault-and-resume*
*Context gathered: 2026-04-28*
