# ArchivistAgent Skills Catalog

**Status:** Draft  
**Audience:** Implementers of ArchivistAgent, vault storage, memory retrieval,
and campaign persistence.  
**Companion specs:** `GAME_SPEC.md` §3.5, `VAULT_SCHEMA.md`,
`STATE_SCHEMA.md`, `PERSISTENCE_SPEC.md`.

## 1. Scope Context

Archivist owns memory read/write behavior, entity resolution, canon guarding,
summary tiers, and the two-vault spoiler-safe projection. It writes the master
vault, syncs the player vault, updates derived read layers, and emits
`CanonConflict` events for Oracle.

Storage surfaces:

- Master vault under app data.
- Player vault under the campaign directory.
- SQLite transcripts, roll logs, checkpoints, and cost logs.
- LanceDB embeddings.
- NetworkX graph.
- SQLite FTS5 index.

The vault is the source of truth for canon. FTS5, LanceDB, and NetworkX are
derived read layers.

## 2. Skills

### 2.1 `memory-packet-assembly`

**Purpose:** Given scene context and player input, assemble a token-bounded
`MemoryPacket` for Oracle and Orator.

**Inputs -> Outputs:** `(scene_context, player_input, token_cap)` ->
`MemoryPacket` containing ranked exact, semantic, graph-neighborhood, callback,
and rolling-summary context.

**Implementation surface:** `hybrid`.

**Key dependencies:** SQLite FTS5, LanceDB, NetworkX, rolling summaries,
`STATE_SCHEMA.md` `MemoryPacket`.

**Success signal:** On a 50-turn fixture, packet size never exceeds the cap and
an NPC introduced early is retrieved correctly when reintroduced later.

### 2.2 `callback-reachability-query`

**Purpose:** Return open callbacks that could plausibly activate in the current
scene, scored by narrative fit.

**Inputs -> Outputs:** `(current_scene, recent_turns, open_callbacks)` ->
`list[(callback_id, fit_score, activation_hints)]`.

**Implementation surface:** `hybrid`.

**Key dependencies:** Master-vault `callbacks/`, active quests, NetworkX graph,
Oracle scene context.

**Success signal:** Fixture scenes with matching location/NPC/quest context
produce non-empty candidate lists and surface the expected callback.

### 2.3 `entity-resolution`

**Purpose:** Resolve whether an incoming named entity already exists in canon
before creating a new vault page.

**Inputs -> Outputs:** `(incoming_name, entity_type, contextual_description)` ->
`match_existing_page_id | create_new`.

**Implementation surface:** `hybrid`.

**Key dependencies:** `VAULT_SCHEMA.md` slug rules, frontmatter aliases,
LanceDB vector similarity.

**Success signal:** Entity-resolution precision is at least `0.95` on the
fixture suite, with zero duplicate NPC pages in a 50-turn regression.

### 2.4 `vault-page-upsert`

**Purpose:** Atomically create or update a master-vault page with valid
frontmatter and preserved GM-only content.

**Inputs -> Outputs:** `(page_type, frontmatter, body, gm_only_blocks)` ->
`(vault_path, created | updated)`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `VAULT_SCHEMA.md` page schemas, atomic write helper,
shared `schema-validation` capability.

**Success signal:** Invalid frontmatter is rejected before disk write; induced
I/O failure leaves no partial canonical page; slug collision creates the
expected suffix.

**Notes / open questions:** Keep separate from `entity-resolution` for now
because read decision and write execution have different failure modes.

### 2.5 `visibility-promotion`

**Purpose:** Promote page visibility one way from `gm_only` to `foreshadowed`
to `player_known` based on in-play events.

**Inputs -> Outputs:** `(page_id, turn_transcript, current_visibility)` ->
`new_visibility | unchanged`.

**Implementation surface:** `prompted`.

**Key dependencies:** `VAULT_SCHEMA.md` visibility states, turn transcript,
page type.

**Success signal:** On labeled visibility fixtures, promotions match gold data
at least `0.9` and no demotions occur.

### 2.6 `canon-conflict-detection`

**Purpose:** Compare player assertions against canon and emit conflicts instead
of silently overwriting facts.

**Inputs -> Outputs:** `(player_input, turn_transcript, relevant_vault_pages)` ->
`list[CanonConflict]`.

**Implementation surface:** `prompted`.

**Key dependencies:** `STATE_SCHEMA.md` `CanonConflict`, memory retrieval,
entity-resolution.

**Success signal:** Crafted conflict fixtures are categorized as retcon intent,
PC misbelief, or narrator error with at least `0.8` accuracy.

**Notes / open questions:** `pending_conflicts: list[CanonConflict]` on
`SagaState` is the proposed handoff to Oracle.

### 2.7 `turn-close-persistence`

**Purpose:** Execute the required turn-close persistence bundle and return a
repairable persistence report.

**Inputs -> Outputs:** `(turn_transcript, state_deltas, changed_pages)` ->
`persistence_report`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `PERSISTENCE_SPEC.md`, SQLite, vault writes, FTS5,
LanceDB, NetworkX.

**Success signal:** A forced crash after SQLite commit but before derived-index
updates is recoverable with `ttrpg vault rebuild`.

### 2.8 `rolling-summary-update`

**Purpose:** Produce a bounded canonical summary at scene boundary or configured
turn cadence for future memory packets.

**Inputs -> Outputs:** `(recent_turns_window, prior_summary, canon_pages_touched)` ->
`updated_summary`.

**Implementation surface:** `prompted`.

**Key dependencies:** Session transcripts, vault pages, content policy,
`PlayerProfile.pacing`.

**Success signal:** Reviewed summaries contain only facts traceable to canon or
confirmed turn events and remain within length bounds.

**Notes / open questions:** Prefer scene-boundary updates once Oracle emits
explicit scene-close events.

### 2.9 `session-page-authoring`

**Purpose:** At session end, create the `sessions/session_NNN.md` page with
summary, beats, entity lists, quest changes, callback changes, and rolls.

**Inputs -> Outputs:** `(session_transcript, session_metadata, canon_changes)` ->
schema-valid session page.

**Implementation surface:** `hybrid`.

**Key dependencies:** SQLite transcript and roll log, touched vault pages,
`VAULT_SCHEMA.md` session schema.

**Success signal:** Frontmatter validates, rolls table reconciles exactly with
the roll log, and beats match Oracle-declared session beats.

### 2.10 `player-vault-sync`

**Purpose:** Project the master vault to the player vault while stripping or
stubbing unrevealed GM-only content.

**Inputs -> Outputs:** `(master_vault_path, player_vault_path, changes_since_last_sync)` ->
`sync_report`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `VAULT_SCHEMA.md` sync contract, visibility states,
GM-only stripping rules, atomic write helper.

**Success signal:** Fixture player vault contains zero GM-only content, all
wikilinks resolve, and all YAML frontmatter parses.

### 2.11 `master-vault-unlock`

**Purpose:** At campaign end, produce the director's-cut vault and epilogue.

**Inputs -> Outputs:** `(campaign_id, player_vault_destination)` ->
`(unlocked_vault_path, epilogue_page)`.

**Implementation surface:** `hybrid`.

**Key dependencies:** Full master vault, campaign seed, callback records,
final faction/NPC/quest state.

**Success signal:** Unlocked vault is valid Obsidian markdown and epilogue
lists every open and paid-off callback.

## 3. Cross-Cutting Dependencies

These capabilities are consumed by Archivist but owned by the shared services
catalog:

- `schema-validation`
- `safety-redline-check`
- atomic write helper
- DiceService roll log interface
- CostGovernor LLM/cost log interface

## 4. Consumers

- Oracle consumes `memory-packet-assembly`, `callback-reachability-query`, and
  `canon-conflict-detection` outputs.
- Orator consumes the assembled `MemoryPacket`.
- RulesLawyer may consume entity lookups for target stat block references.
- The TUI consumes sync and repair warnings from `turn-close-persistence` and
  `player-vault-sync`.
