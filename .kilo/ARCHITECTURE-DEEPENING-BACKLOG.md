# Architecture Deepening Backlog

This file is coding-harness output from architecture review. It is not
SagaSmith product/runtime context.

Use this file to preserve deepening opportunities discovered by Kilo skills.
Promote an item into a SagaSmith spec or ADR only after the user accepts the
design direction.

## Known Deepening Opportunities

These use the architecture vocabulary from the `improve-codebase-architecture`
skill: Module, Interface, Seam, Adapter, Depth, Leverage, and Locality.

### 1. Provider Runtime Module

**Status:** Implemented in `src/sagasmith/providers/runtime.py`. Keep this item
for historical context and future follow-up if provider startup expands beyond
fake/OpenRouter.

**Files:** `src/sagasmith/cli/configure_cmd.py`,
`src/sagasmith/tui/runtime.py`, `src/sagasmith/app/config.py`,
`src/sagasmith/providers/openrouter.py`, `src/sagasmith/providers/fake.py`,
`src/sagasmith/providers/runtime.py`

**Problem:** Provider settings can be persisted, but TUI startup still wires
`llm=None` into graph bootstrap. The current Interface is Shallow because
callers must know separate facts about settings, secrets, provider selection,
and graph injection.

**Solution:** Create a Provider Runtime Module with one Interface such as
"build the LLM Adapter for this opened campaign." The Module should load
`ProviderSettings`, resolve `SecretRef`, choose the correct Adapter, and return
either a live LLM Adapter or a typed startup error. Fake and OpenRouter are two
real Adapters at this Seam, so the Seam is justified.

**Benefits:** This concentrates secret handling and provider startup failures
in one place, giving better Locality. It gives Leverage because CLI play, smoke
paths, tests, and future direct providers can all cross the same Interface.
Tests should verify the Interface with fake and OpenRouter-like Adapters
without touching TUI runtime internals.

### 2. Canonical Turn History Module

**Status:** Implemented in `src/sagasmith/persistence/turn_history.py`. `TurnStatus`
constants added to `src/sagasmith/schemas/persistence.py`. All 7 canonical-read
callsites migrated; two unfiltered-session-count bugs fixed. Tests at
`tests/persistence/test_turn_history.py`.

**Files:** `src/sagasmith/persistence/repositories.py`,
`src/sagasmith/cli/play_cmd.py`, `src/sagasmith/tui/runtime.py`,
`src/sagasmith/tui/app.py`,
`src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py`,
`src/sagasmith/persistence/retcon.py`

**Problem:** Canonical-turn filtering exists in some repositories, but direct
SQL still appears for latest turn, scrollback, session turns, sync warnings,
and session page source rows. This makes the retcon invariant depend on
scattered query knowledge.

**Solution:** Create a Canonical Turn History Module that owns completed
canonical reads and related history queries: recent transcript context, latest
canonical turn, next session number, session page source turns, and warning
lookups. Audit/debug reads can opt into retconned data explicitly.

**Benefits:** Retcon correctness gains Locality because canonical exclusion is
defined once. Callers get Leverage from simple history queries that already
apply the correct status rules. Tests should target this Module's Interface,
especially completed vs. retconned turn behavior.

### 3. Turn Start Module

**Status:** Implemented in `src/sagasmith/turn_start/builder.py`. `_build_play_state`
shim retained as a one-line delegate pending Step B deletion. Tests at
`tests/turn_start/test_builder.py`.

**Files:** `src/sagasmith/tui/app.py`,
`src/sagasmith/graph/runtime.py`,
`src/sagasmith/schemas/saga_state.py`,
`src/sagasmith/rules/first_slice.py`

**Problem:** `SagaSmithApp._build_play_state()` currently knows graph-state
defaults, turn progression, phase selection, first-slice character seeding,
cost state shape, combat carryover, and narration/check-result carryover. The
TUI Interface is too broad because UI code must know graph invariants.

**Solution:** Move play-turn state construction into a Turn Start Module. The
Interface should accept the campaign/session context, optional current graph
snapshot values, current cost state, and player input, then return a valid
state dict or `SagaState`.

**Benefits:** State-shape changes gain Locality. The TUI gets Leverage by
delegating graph invariants to one Module. Tests can cover fresh turn,
continued combat, resumed narration/check-results, and first-slice sheet
seeding through the Turn Start Interface instead of Textual UI paths.

### 4. Archivist Turn Plan Module

**Status:** Implemented in `src/sagasmith/turn_plan/builder.py`. `archivist_node`
retained as a ~70-line LangGraph Adapter shim. Entity-type map consolidated into
`src/sagasmith/vault/page_types.py`. Tests at `tests/turn_plan/test_builder.py`.

**Files:** `src/sagasmith/agents/archivist/node.py`,
`src/sagasmith/persistence/turn_close.py`,
`src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py`,
`src/sagasmith/agents/archivist/skills/vault_page_upsert/logic.py`,
`src/sagasmith/agents/archivist/skills/visibility_promotion/logic.py`,
`src/sagasmith/agents/archivist/skills/rolling_summary_update/logic.py`

**Problem:** The Archivist node is pure, which matches ADR-0001, but the node
Implementation still coordinates many concepts: world bible vault pages,
campaign seed vault pages, entity resolution, visibility promotion, rolling
summary updates, canon conflict detection, memory packet assembly, and vault
write serialization. The node has become a Shallow Interface over a large
workflow.

**Solution:** Create an Archivist Turn Plan Module behind the node. The node
remains the LangGraph Adapter, while the deeper Module owns the pure workflow
and returns an explicit turn plan: memory packet, rolling summary, pending
conflicts, pending vault writes, and state updates.

**Benefits:** Archivist behavior gains Locality without violating the ADR that
nodes stay pure. Callers get Leverage from a small Interface that hides the
skill coordination. Tests should exercise the Archivist Turn Plan Interface
with in-memory/fake vault Adapters and then keep node tests thin.

### 5. Retcon Repair Module

**Status:** Implemented in `src/sagasmith/retcon_repair/repair.py`.
`GraphRuntime.confirm_retcon` retained as a ~15-line Adapter shim.
Duplicate FTS5+graph rebuild bug fixed. `RetconRepairError` (with `stage`
attribute) distinguishes post-commit repair failures from pre-commit
`RetconBlockedError` vetoes. Tests at `tests/retcon_repair/test_repair.py`.

**Files:** `src/sagasmith/graph/runtime.py`,
`src/sagasmith/persistence/retcon.py`, `src/sagasmith/vault/__init__.py`,
`src/sagasmith/memory/fts5.py`, `src/sagasmith/memory/graph.py`

**Problem:** Retcon status and audit have Depth, but repair orchestration is
Shallow. `GraphRuntime.confirm_retcon()` owns checkpoint rewind, derived-index
rebuild, vault rebuild, graph-cache warming, and player-vault projection sync.
That makes graph runtime know too much about repair ordering and canonical
source selection.

**Solution:** Create a Retcon Repair Module that owns repair from canonical
sources. Keep `GraphRuntime` as the Adapter for checkpoint movement, while the
deeper Module handles vault/index/player-projection repair and safe failure
reporting.

**Benefits:** Retcon repair rules gain Locality. CLI repair, TUI retcon, smoke
checks, and future audit tooling get Leverage through one repair Seam. Tests can
target canonical-source repair directly instead of driving graph runtime.

### 6. Session Page Authoring Module

**Status:** Implemented. `CanonicalTurnHistory.session_page_source()` owns
canonical source-row selection. `draft_session_page()` now returns a `VaultPage`
draft without SQLite or vault write Adapters. `apply_vault_writes()` applies and
audits session page writes through the same turn-close vault-write Seam. Tests
cover source rows, drafting, audited writes, and quit/resume integration.

**Files:**
`src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py`,
`src/sagasmith/graph/runtime.py`, `src/sagasmith/persistence/turn_close.py`,
`src/sagasmith/persistence/turn_history.py`

**Problem:** Session page authoring reads SQLite directly, filters canonical
turns locally, formats a vault page, writes directly to the vault, and returns
only a path. This bypasses the audited vault-write Seam used by turn close and
duplicates Canonical Turn History knowledge.

**Solution:** Deepen session page authoring so it produces a session page draft
from Canonical Turn History. Let the persistence/vault write Module apply and
audit the draft through the same vault-write Seam as other turn-close pages.

**Benefits:** Canonical filtering and vault audit ordering gain Locality.
Session pages, repair, and rebuild get Leverage from the same draft/write flow.
Tests can separately verify source-row selection, page drafting, and audited
writing.

### 7. Oracle Scene Planning Module

**Files:** `src/sagasmith/agents/oracle/node.py`,
`src/sagasmith/agents/oracle/skills/scene_brief_composition/logic.py`,
`src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py`,
`src/sagasmith/services/safety_pre_gate.py`

**Problem:** `oracle_node()` handles campaign context generation, memory packet
assembly, player-choice branching, safety pre-gate, fallback scene brief
creation, budget interrupt shaping, provider model selection, and skill
activation. The node Interface is nearly as complex as its Implementation.

**Solution:** Create an Oracle Scene Planning Module behind the node. The node
remains the LangGraph Adapter, while the deeper Module owns the planning
decision and returns explicit state updates or interrupts.

**Benefits:** Planning behavior gains Locality. Provider-backed and
provider-free planning get Leverage through one Seam. Tests can target scene
planning outcomes without graph activation scaffolding.

### 8. Safety Guard Module

**Files:** `src/sagasmith/services/safety_pre_gate.py`,
`src/sagasmith/services/safety_post_gate.py`,
`src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py`,
`src/sagasmith/agents/orator/skills/scene_rendering/logic.py`

**Problem:** Safety policy logic is split across pre-gate, post-gate, Oracle
routing, and Orator inline/rewrite behavior. Synonym and regex policy knowledge
is duplicated, so a safety rule change can miss one scanner.

**Solution:** Create a Safety Guard Module that owns pre-generation routing,
inline streaming scan, post-generation scan, event construction, and
rewrite/fallback policy.

**Benefits:** Safety regressions gain Locality. Callers get Leverage from one
policy Interface instead of multiple partial scanners. Tests can run hard-limit,
soft-limit, streaming, and rewrite cases through the same Seam.

### 9. Rules Turn Resolution Module

**Files:** `src/sagasmith/agents/rules_lawyer/node.py`,
`src/sagasmith/services/intent_resolution.py`,
`src/sagasmith/services/rules_engine.py`,
`src/sagasmith/services/combat_engine.py`, `src/sagasmith/rules/first_slice.py`

**Problem:** The deterministic rules Modules have useful Depth, but
`rules_lawyer_node()` owns parsing, intent fallback, skill activation,
first-slice defaults, rules engine construction, combat engine construction,
error wording, phase changes, and narration audit messages.

**Solution:** Create a Rules Turn Resolution Module that owns one player rules
turn. Keep the node as the LangGraph Adapter.

**Benefits:** PF2e first-slice behavior gains Locality. TUI, replay, smoke
tests, and future rules inputs get Leverage through one Interface. Tests can
exercise rules-turn results directly instead of graph-node dictionaries.

### 10. Agent Skills Execution Module

**Files:** `src/sagasmith/skills_adapter/store.py`,
`src/sagasmith/skills_adapter/loader.py`, `src/sagasmith/graph/bootstrap.py`,
`src/sagasmith/agents/*/node.py`

**Problem:** Skill discovery and validation have Depth, but runtime Leverage is
low. Nodes often import skill Implementations directly and use the skill store
mostly for authorization/logging, which underuses the Agent Skills Seam from
ADR-0001.

**Solution:** Create an Agent Skills Execution Module so nodes consistently
discover, authorize, load instructions, and invoke deterministic skill
Implementations through one Module.

**Benefits:** ADR-0001 alignment improves. Skill authorization, activation, and
execution gain Locality. Tests can exercise skill behavior through the same
Interface nodes use.
