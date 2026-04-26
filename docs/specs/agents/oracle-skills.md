# OracleAgent Skills Catalog

**Status:** Draft  
**Audience:** Implementers of scene planning, world seeding, campaign hooks,
encounter requests, pacing, and callback management.  
**Companion specs:** `GAME_SPEC.md` §3.2, `STATE_SCHEMA.md`,
`VAULT_SCHEMA.md`, `PF2E_MVP_SUBSET.md`.

## 1. Scope Context

Oracle is the GM planner. It creates world structure and scene briefs, tracks
hooks and callbacks, requests encounter validation from RulesLawyer, and adapts
to player choices. Oracle never narrates directly to the player.

## 2. Skills

### 2.1 `world-bible-generation`

**Purpose:** Create the initial hidden campaign world bible from onboarding
records.

**Inputs -> Outputs:** `(PlayerProfile, ContentPolicy, HouseRules)` ->
`WorldBible` vault/meta artifact.

**Implementation surface:** `prompted`.

**Key dependencies:** Onboarding outputs, Archivist `vault-page-upsert`,
content policy.

**Success signal:** Generated world bible validates, avoids hard limits, and
contains enough locations/NPC/factions to seed the first hook set.

### 2.2 `campaign-seed-generation`

**Purpose:** Produce 3-5 opening plot hooks and one selected seed arc.

**Inputs -> Outputs:** `(WorldBible, PlayerProfile)` -> `CampaignSeed`.

**Implementation surface:** `prompted`.

**Key dependencies:** `world-bible-generation`, Archivist vault writes.

**Success signal:** Hook fixtures produce distinct hooks aligned with player
pillar weights and tone.

### 2.3 `scene-brief-composition`

**Purpose:** Build a structured `SceneBrief` for the next playable scene.

**Inputs -> Outputs:** `(SagaState, MemoryPacket, pending_conflicts)` ->
`SceneBrief`.

**Implementation surface:** `prompted`.

**Key dependencies:** `STATE_SCHEMA.md` `SceneBrief`, Archivist memory packet,
content policy.

**Success signal:** Every brief includes required fields and never contains
player-facing narration.

### 2.4 `player-choice-branching`

**Purpose:** Update scene direction when the player accepts, rejects, bypasses,
or reframes a planned beat.

**Inputs -> Outputs:** `(player_input, prior_scene_brief, memory_packet)` ->
revised scene intent or next brief request.

**Implementation surface:** `prompted`.

**Key dependencies:** recent transcript, player profile pacing.

**Success signal:** Bypass fixtures produce coherent replans without forcing
the original beat.

### 2.5 `callback-seeding`

**Purpose:** Seed future payoff opportunities without overloading the callback
ledger.

**Inputs -> Outputs:** `(scene_brief, campaign_seed, backlog)` -> callback page
drafts or no-op.

**Implementation surface:** `hybrid`.

**Key dependencies:** Archivist callback pages, callback ledger size.

**Success signal:** A five-session fixture contains at least one seed-to-payoff
cycle and avoids unbounded callback growth.

### 2.6 `callback-payoff-selection`

**Purpose:** Prefer resolving reachable older callbacks when they fit the
current scene.

**Inputs -> Outputs:** `(reachability_candidates, scene_context)` -> selected
callback payoff or no-op.

**Implementation surface:** `prompted`.

**Key dependencies:** Archivist `callback-reachability-query`.

**Success signal:** Fixture scenes with a strong reachable callback choose
payoff over seeding a new unrelated callback.

### 2.7 `inline-npc-creation`

**Purpose:** Create small-scope NPCs inline for current scenes while preserving
future consistency through Archivist.

**Inputs -> Outputs:** `(scene_need, world_context, content_policy)` -> NPC
page draft.

**Implementation surface:** `prompted`.

**Key dependencies:** Archivist `entity-resolution`, `vault-page-upsert`.

**Success signal:** NPC drafts include name, role, voice, disposition, and safe
secret handling; duplicate NPC names are resolved instead of recreated.

### 2.8 `encounter-request-composition`

**Purpose:** Request a mechanically valid encounter from available creature
data and scene context.

**Inputs -> Outputs:** `(party_level, desired_difficulty, terrain_tags)` ->
encounter proposal for RulesLawyer validation.

**Implementation surface:** `hybrid`.

**Key dependencies:** `PF2E_MVP_SUBSET.md`, RulesLawyer
`encounter-budget-validation`.

**Success signal:** Proposed encounters validate or are revised until valid;
Oracle never bypasses mechanical validation.

### 2.9 `content-policy-routing`

**Purpose:** Adjust scene plans before narration when intent risks hard or soft
content limits.

**Inputs -> Outputs:** `(scene_intent, ContentPolicy)` -> allowed scene intent
or reroute.

**Implementation surface:** `hybrid`.

**Key dependencies:** SafetyGuard pre-gate, content policy.

**Success signal:** Redlined fixture intents are rerouted before Orator sees
them.

### 2.10 `pacing-calibration`

**Purpose:** Tune scene length, tension, and pillar emphasis to player
preferences and recent play history.

**Inputs -> Outputs:** `(PlayerProfile, recent_session_stats)` ->
`PacingTarget`.

**Implementation surface:** `prompted`.

**Key dependencies:** player profile, transcript metrics, session state.

**Success signal:** A combat-heavy recent window with low combat preference
causes the next brief to shift emphasis away from combat.

### 2.11 `canon-conflict-response`

**Purpose:** Incorporate Archivist `CanonConflict` events into the next plan
without silently changing canon.

**Inputs -> Outputs:** `(pending_conflicts, current_scene)` -> brief adjustment
or player-facing clarification instruction for Orator.

**Implementation surface:** `prompted`.

**Key dependencies:** Archivist `canon-conflict-detection`.

**Success signal:** Conflict fixtures surface contradictions explicitly and do
not overwrite vault facts.

## 3. First-Slice Required Skills

The first vertical slice requires:

- `scene-brief-composition`
- `player-choice-branching`
- `content-policy-routing`
- minimal `inline-npc-creation`

World bible, campaign seed, callbacks, and encounter composition may use canned
fixture content until persistence and mechanics are ready.
