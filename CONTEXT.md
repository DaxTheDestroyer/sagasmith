# SagaSmith Context

## Domain Terms

### Campaign Reference

A user-facing value that identifies a local campaign. It may be a campaign
directory path, a campaign slug, or a display name that can be resolved to one
local campaign directory.

### Provider Runtime

The startup path that turns persisted provider settings into a live LLM adapter
for graph execution. It owns loading `ProviderSettings`, resolving `SecretRef`,
choosing the fake or OpenRouter adapter, and surfacing startup failures without
leaking secrets.

### Canonical Turn History

The canonical read model for completed, non-retconned campaign history. It owns
latest-turn status, recent transcript context, next session number, session-page
source rows, and any query where retconned turns must be excluded by default.

### Turn Start

The construction of a valid play-turn graph state from a campaign, session,
current graph snapshot, and player input. It owns turn ID progression, phase
selection, default first-slice character state, cost state, combat carryover,
and narration/check-result carryover.

### Archivist Turn Plan

The pure Archivist workflow for one turn-close preparation pass. It decides
which memory packet, rolling summary, canon conflicts, visibility promotions,
and vault page writes should be returned to the graph runtime for persistence.

## Architecture Deepening Backlog

These are follow-up opportunities from the `improve-codebase-architecture`
review. They use the architecture vocabulary from that skill: module,
interface, seam, adapter, depth, leverage, and locality.

### 1. Provider Runtime Module

**Files:** `src/sagasmith/cli/configure_cmd.py`,
`src/sagasmith/tui/runtime.py`, `src/sagasmith/app/config.py`,
`src/sagasmith/providers/openrouter.py`, `src/sagasmith/providers/fake.py`

**Problem:** Provider settings can be persisted, but TUI startup still wires
`llm=None` into graph bootstrap. The current interface is shallow because
callers must know separate facts about settings, secrets, provider selection,
and graph injection.

**Solution:** Create a Provider Runtime module with one interface such as
"build the LLM adapter for this opened campaign." The module should load
`ProviderSettings`, resolve `SecretRef`, choose the correct adapter, and return
either a live LLM adapter or a typed startup error. Fake and OpenRouter are two
real adapters at this seam, so the seam is justified.

**Benefits:** This concentrates secret handling and provider startup failures
in one place, giving better locality. It gives leverage because CLI play, smoke
paths, tests, and future direct providers can all cross the same interface.
Tests should verify the interface with fake and OpenRouter-like adapters
without touching TUI runtime internals.

### 2. Canonical Turn History Module

**Files:** `src/sagasmith/persistence/repositories.py`,
`src/sagasmith/cli/play_cmd.py`, `src/sagasmith/tui/runtime.py`,
`src/sagasmith/tui/app.py`,
`src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py`,
`src/sagasmith/persistence/retcon.py`

**Problem:** Canonical-turn filtering exists in some repositories, but direct
SQL still appears for latest turn, scrollback, session turns, sync warnings,
and session page source rows. This makes the retcon invariant depend on
scattered query knowledge.

**Solution:** Create a Canonical Turn History module that owns completed
canonical reads and related history queries: recent transcript context, latest
canonical turn, next session number, session page source turns, and warning
lookups. Audit/debug reads can opt into retconned data explicitly.

**Benefits:** Retcon correctness gains locality because canonical exclusion is
defined once. Callers get leverage from simple history queries that already
apply the correct status rules. Tests should target this module's interface,
especially completed vs. retconned turn behavior.

### 3. Turn Start Module

**Files:** `src/sagasmith/tui/app.py`,
`src/sagasmith/graph/runtime.py`,
`src/sagasmith/schemas/saga_state.py`,
`src/sagasmith/rules/first_slice.py`

**Problem:** `SagaSmithApp._build_play_state()` currently knows graph-state
defaults, turn progression, phase selection, first-slice character seeding,
cost state shape, combat carryover, and narration/check-result carryover. The
TUI interface is too broad because UI code must know graph invariants.

**Solution:** Move play-turn state construction into a Turn Start module. The
interface should accept the campaign/session context, optional current graph
snapshot values, current cost state, and player input, then return a valid
state dict or `SagaState`.

**Benefits:** State-shape changes gain locality. The TUI gets leverage by
delegating graph invariants to one module. Tests can cover fresh turn,
continued combat, resumed narration/check-results, and first-slice sheet
seeding through the Turn Start interface instead of Textual UI paths.

### 4. Archivist Turn Plan Module

**Files:** `src/sagasmith/agents/archivist/node.py`,
`src/sagasmith/persistence/turn_close.py`,
`src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py`,
`src/sagasmith/agents/archivist/skills/vault_page_upsert/logic.py`,
`src/sagasmith/agents/archivist/skills/visibility_promotion/logic.py`,
`src/sagasmith/agents/archivist/skills/rolling_summary_update/logic.py`

**Problem:** The Archivist node is pure, which matches ADR-0001, but the node
implementation still coordinates many concepts: world bible vault pages,
campaign seed vault pages, entity resolution, visibility promotion, rolling
summary updates, canon conflict detection, memory packet assembly, and vault
write serialization. The node has become a shallow interface over a large
workflow.

**Solution:** Create an Archivist Turn Plan module behind the node. The node
remains the LangGraph adapter, while the deeper module owns the pure workflow
and returns an explicit turn plan: memory packet, rolling summary, pending
conflicts, pending vault writes, and state updates.

**Benefits:** Archivist behavior gains locality without violating the ADR that
nodes stay pure. Callers get leverage from a small interface that hides the
skill coordination. Tests should exercise the Archivist Turn Plan interface
with in-memory/fake vault adapters and then keep node tests thin.
