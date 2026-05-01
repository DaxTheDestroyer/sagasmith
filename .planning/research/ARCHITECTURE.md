# Architecture Patterns: SagaSmith

**Domain:** Local-first multi-agent AI TTRPG runtime  
**Researched:** 2026-04-26  
**Overall confidence:** HIGH for project-specific architecture because core constraints are specified in-repo; MEDIUM for LangGraph/Textual integration details pending implementation spike.

## System Shape

SagaSmith should be structured as a **local-first event-driven TUI shell around a LangGraph turn engine**, with deterministic services below the graph and storage adapters below those services. The central rule is: **LLM agents propose, interpret, plan, summarize, and narrate; deterministic services validate, resolve, persist, account, and write files.**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Textual TUI                                                                  │
│ - streaming transcript, input, status, dice overlay, safety bar              │
│ - dispatches commands and displays graph events; does not own game state     │
└───────────────┬──────────────────────────────────────────────────────────────┘
                │ PlayerInput / SlashCommand / InterruptResume
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Application Runtime                                                          │
│ - campaign bootstrap, session manager, config, dependency container          │
│ - starts graph runs in Textual workers and forwards stream/update events     │
└───────────────┬──────────────────────────────────────────────────────────────┘
                │ SagaState + thread_id(campaign/session)
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ LangGraph Orchestration Layer                                                │
│ - typed StateGraph[SagaState]                                                │
│ - nodes: Onboarding, ArchivistRead, Oracle, RulesLawyer, Orator,             │
│   ArchivistWrite/Persist, Safety, Command/Interrupt handlers                 │
│ - conditional routing by phase, command, combat state, safety/cost events    │
│ - streaming + updates + interrupts + checkpointing                           │
└──────┬─────────────┬──────────────┬──────────────┬───────────────────────────┘
       │             │              │              │
       ▼             ▼              ▼              ▼
┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────────────────────────┐
│ LLMClient  │ │ Agent Skills │ │ Services   │ │ Persistence + Memory          │
│ abstraction│ │ SkillStore   │ │ deterministic│ │ SQLite, master vault,         │
│ OpenRouter │ │ load_skill   │ │/bounded hybrid│ │ player vault, FTS5, LanceDB,  │
│ first      │ │ catalog      │ │ rules/safety │ │ NetworkX                      │
└────────────┘ └──────────────┘ └────────────┘ └───────────────────────────────┘
```

### Recommended Package Shape

```text
sagasmith/
├── app/                         # CLI entrypoints, app bootstrap, dependency wiring
│   ├── cli.py
│   ├── config.py
│   ├── session.py
│   └── runtime.py
├── tui/                         # Textual UI only
│   ├── app.py
│   ├── screens/
│   ├── widgets/
│   └── events.py
├── graph/                       # LangGraph orchestration only
│   ├── state.py                 # SagaState reducers + Pydantic/TypedDict bridge
│   ├── build.py                 # StateGraph construction
│   ├── routing.py               # conditional edges
│   ├── events.py                # stream/update event normalization
│   └── nodes/
│       ├── onboarding.py
│       ├── archivist_read.py
│       ├── oracle.py
│       ├── rules_lawyer.py
│       ├── orator.py
│       ├── safety.py
│       └── persist.py
├── agents/                      # prompts and per-agent adapters; no direct disk writes
│   ├── onboarding/
│   ├── oracle/
│   ├── rules_lawyer/
│   ├── archivist/
│   └── orator/
├── skills/                      # cross-cutting Agent Skills packages
├── services/                    # deterministic and bounded-hybrid capabilities
│   ├── rules/                   # PF2e deterministic engine
│   ├── dice.py
│   ├── intent.py
│   ├── safety.py
│   ├── cost.py
│   ├── validation.py
│   ├── commands.py
│   └── atomic_files.py
├── providers/                   # LLMClient implementations and model config
│   ├── base.py
│   ├── openrouter.py
│   └── pricing.py
├── persistence/                 # SQLite + repositories + LangGraph saver wiring
│   ├── db.py
│   ├── repositories.py
│   ├── checkpoints.py
│   └── migrations/
├── memory/                      # vault and retrieval derived layers
│   ├── vault.py
│   ├── projection.py
│   ├── fts.py
│   ├── embeddings.py
│   ├── graph_index.py
│   └── retrieval.py
├── schemas/                     # Pydantic models / JSON Schema export
└── evals/                       # replay, fixture, safety, memory, smoke harnesses
```

**Opinionated recommendation:** keep `graph/` thin. Graph nodes should orchestrate calls to `agents/`, `services/`, and `memory/`; they should not contain PF2e math, SQLite SQL, vault parsing, provider-specific API logic, or Textual widget logic.

### Graph Shape

Use a typed LangGraph `StateGraph` as the single turn coordinator. Context7 LangGraph docs confirm Python LangGraph supports durable workflows, streaming modes, checkpoint-backed threads, human-in-the-loop interrupts, and replay/time-travel behavior. That matches SagaSmith's per-turn checkpoint, `/pause`, `/line`, and resume requirements.

Recommended MVP node topology:

```text
START
  │
  ▼
command_or_input_gate
  ├─ slash command ───────────────► command_handler ─► interrupt_or_service_result
  └─ player action
        │
        ▼
safety_pre_gate
        │
        ▼
archivist_read                 # builds MemoryPacket; no canon writes
        │
        ▼
oracle_plan                    # produces/revises SceneBrief; never narrates
        │
        ▼
intent_and_rules_gate
        ├─ no mechanics ─────────► orator_stream
        └─ mechanics needed ─────► rules_lawyer_resolve ─► dice_interrupt? ─► orator_stream
                                        │
                                        ▼
                                  deterministic rules engine
        │
        ▼
safety_post_gate               # validates player-facing prose; rewrite/fallback if needed
        │
        ▼
archivist_write_and_persist     # transcript, roll log, checkpoint, vault, indices, projection
        │
        ▼
END / prompt_returned
```

For onboarding and character creation, use separate phase routes within the same graph, not a separate orchestration system:

```text
phase=onboarding          → onboarding_node → validate_profile_records → persist_profile
phase=character_creation  → character_builder_or_pregen → rules_validate_sheet → persist_sheet
phase=play/combat         → normal turn graph above
phase=paused              → interrupt handler / command handler
phase=session_end         → session page authoring → final checkpoint
```

## Component Boundaries

| Component | Responsibility | Owns | Must Not Own | Communicates With |
|---|---|---|---|---|
| Textual TUI | Render terminal UI, collect input, display stream/update events, show dice and safety overlays | Widget state, transient input buffers, display-only transcript buffer | Canon, PF2e rules, SQLite transactions, vault writes, provider calls | App runtime via typed UI events |
| CLI/App Runtime | Bootstrap campaign, open DB, load config/key refs, wire dependencies, start/stop graph threads | Process lifecycle, dependency container, session identity | Game rules, agent prompts, vault semantics | TUI, graph, persistence, providers |
| LangGraph `StateGraph` | Coordinate turn order, route by phase/commands/combat/safety/cost, checkpoint compact `SagaState` | Graph control flow, `SagaState` merge/reducer semantics, interrupt boundaries | Business logic internals, raw vault bodies, direct UI widgets | Nodes, checkpointer, app runtime |
| `SagaState` schemas | Compact cross-node state and references | Current phase, IDs, compact payloads, pending results/events | Full transcript history, full vault contents, plaintext secrets | Graph nodes, SQLite checkpoint saver |
| Onboarding node | Conduct setup interview and produce `PlayerProfile`, `ContentPolicy`, `HouseRules` | Prompted interview flow and structured outputs | Persistence commit semantics, secret storage | LLMClient, schema validation, persistence repo |
| Oracle node | GM planning: scene briefs, world/seed planning, callbacks, encounter requests | `SceneBrief`, world/campaign drafts, callback intentions | Player-facing narration, mechanics math, vault writes | MemoryPacket, SafetyGuard, RulesLawyer validation, Archivist write |
| RulesLawyer node | Translate intent into check proposals and call deterministic rules services | Mechanical intent mapping and result packaging | Dice RNG internals, PF2e formulas in prompts, narration | IntentResolver, PF2e engine, DiceService, Oracle/Orator |
| PF2e rules engine | Deterministic rules math: degree of success, strikes, initiative, action economy, HP/effects | Rules tables, stat calculations, state deltas, validation errors | Narrative prose, LLM calls, vault writes | RulesLawyer node, DiceService, schemas |
| Orator node | Sole player-facing narrative voice; stream prose from resolved plans/mechanics/memory | Narration prompts, streamed text, optional late roll request | Scene planning authority, canon writes, mechanics contradiction | LLMClient stream, SafetyGuard, RulesLawyer for late roll |
| Archivist read path | Assemble bounded `MemoryPacket`; entity/callback lookup | Retrieval ranking, summary selection, entity refs | Mutating canon during read | Vault read models, FTS5, LanceDB, NetworkX, SQLite transcripts |
| Archivist write path | Extract canon changes, detect conflicts, author/update pages, summaries, player projection | Canon change proposals, vault page drafts, conflict events | SQLite transaction order itself unless wrapped by persistence service | PersistenceService, VaultStore, SafetyGuard, Oracle |
| PersistenceService | Enforce turn-close ordering and recovery semantics | SQLite transactions, checkpoint writes, log rows, repair flags | Agent reasoning, PF2e math, narrative policy | Graph persist node, repos, VaultStore, indexers |
| VaultStore | Atomic master-vault page IO and validation | Markdown parsing, YAML frontmatter, slug paths, `os.replace()` writes | Deciding what facts are canon | Archivist, PersistenceService |
| PlayerVaultProjector | Spoiler-safe projection from master to player vault | GM-only stripping, foreshadowed stubs, index/log regeneration | Canon source of truth | PersistenceService, VaultStore, SafetyGuard |
| Retrieval indices | Rebuildable read layers | FTS5 exact search, LanceDB semantic search/entity similarity, NetworkX topology | Canonical facts | Archivist read/write, rebuild commands |
| LLMClient | Provider-neutral completion/stream API, retries, usage metadata | Request/response normalization, provider IDs, streaming events | Budget policy decisions, secrets persistence, prompt construction | Agents, CostGovernor, llm-call-logging |
| CostGovernor | Token/cost accounting and hard-stop decisions | `CostState`, warning/hard-stop events | Provider API transport | LLMClient logs, graph routing, TUI status |
| SafetyGuard | Pre-gate scene intents and post-gate player-visible text/artifacts | Safety decisions, rewrite/fallback events | General moderation as an agent persona | Oracle, Orator, player-vault sync, graph routing |
| SkillStore / Agent Skills adapter | Progressive disclosure for per-agent capability docs | Skill discovery metadata, `load_skill` tool, activation logs | Orchestration routing, persistence, direct user UI | Agent nodes, eval harness |

### Boundary Rules That Should Become Code Review Checks

1. **No provider SDK imports outside `providers/`.** Agents receive an `LLMClient` protocol.
2. **No Textual imports outside `tui/` and app bootstrap glue.** Graph and services emit neutral events.
3. **No vault file writes outside `memory/vault.py` or `persistence` transaction orchestration.** Archivist drafts content; VaultStore writes it.
4. **No random dice outside `DiceService`.** PF2e engine gets `RollResult`s through seeded dice only.
5. **No plaintext API keys in `SagaState`, SQLite logs, transcripts, vault pages, checkpoints, or debug events.** Store keyring/env references only.
6. **No LLM-authored mechanics deltas without deterministic validation.** A `StateDelta(source="rules")` must trace to the PF2e engine, not prose.
7. **No Orator scene planning.** If it discovers a late mechanical need, it emits a `RollRequest`/interrupt rather than deciding outcome itself.

## Data Flow

### Startup / Resume Flow

```text
CLI command
  → load app config and key references
  → open campaign SQLite DB
  → initialize repositories and LangGraph SQLite checkpointer
  → load compact latest checkpoint for campaign/session thread
  → validate schema versions and migrations
  → initialize VaultStore paths
  → initialize/rebuild derived indices if flagged stale
  → mount Textual app
  → render resume screen or first prompt
```

**Direction:** persistent state flows upward into the runtime; the TUI receives a display model only. The UI should never independently inspect master vault files.

### Normal Player Turn Flow

```text
1. TUI captures input
   → CommandDispatch classifies slash command vs normal action.

2. App runtime starts graph run in a Textual worker
   → graph.astream(..., stream_mode=["messages", "updates"])
   → UI receives normalized events, not raw graph internals.

3. Graph command/input gate
   → slash commands route to command handlers or interrupts
   → normal actions continue to safety pre-gate.

4. Safety pre-gate
   → blocks/reroutes hard-limit scene intents before Oracle/Orator generation.

5. Archivist read path
   → queries SQLite transcripts, master vault, FTS5, LanceDB, NetworkX
   → emits bounded MemoryPacket into SagaState.

6. Oracle plan
   → consumes PlayerProfile, ContentPolicy, HouseRules, SessionState,
     MemoryPacket, pending CanonConflict events, and player input
   → emits SceneBrief and optional encounter/callback/page drafts
   → does not narrate and does not write disk.

7. Intent/rules resolution
   → IntentResolver maps player action to mechanical candidates
   → RulesLawyer node calls deterministic PF2e engine
   → DiceService produces seeded RollResult
   → engine emits CheckResult and replayable StateDelta list.

8. Orator stream
   → consumes SceneBrief, MemoryPacket, resolved CheckResult list, tone/policy
   → streams player-facing prose through LLMClient.stream
   → Textual app appends stream tokens to a noncanonical transcript buffer.

9. Safety post-gate
   → approves generated prose or requests bounded rewrite/fallback
   → logs SafetyEvent.

10. Turn-close persistence
   → see ordered flow below.

11. TUI status refresh
   → display model updates HP, conditions, clock, budget, last rolls, repair warnings
   → prompt returns.
```

### Turn-Close Persistence Flow

Must follow `PERSISTENCE_SPEC.md` ordering exactly:

```text
Begin SQLite transaction
  → append transcript records
  → append roll logs
  → append redacted LLM call logs
  → store applied StateDeltas
  → store LangGraph final checkpoint through SQLite saver
Commit SQLite transaction
  → atomic master-vault writes
  → update derived indices: FTS5, LanceDB, NetworkX
  → sync player vault projection
  → emit persistence/sync report to TUI
```

**Important implication:** the final checkpoint is part of the SQLite transaction, but master vault writes occur after commit. Therefore recovery must tolerate SQLite being ahead of the vault. If vault write fails, mark `needs_vault_repair` and skip derived sync. If derived index or player vault sync fails, the turn is still complete and repair commands handle rebuild/sync.

### Streaming and Interrupt Flow

Use LangGraph streaming for node updates and LLM message chunks, and Textual workers for non-blocking UI:

```text
Textual input submit
  → start graph worker
  → async iterate graph stream events
  → on message chunk: append token to transcript widget
  → on update: update status/dice/safety panels
  → on interrupt: pause graph worker display, show modal, resume with Command(resume=...)
```

Context7 Textual docs confirm Textual workers are the right concurrency primitive for long-running or streaming calls, and `call_from_thread` is required when updating UI safely from thread workers. Prefer async workers when provider and LangGraph calls are async-compatible; use thread workers only around blocking provider SDKs or file-heavy rebuild commands.

### `/pause`, `/line`, `/retcon`, and Late-Roll Flow

| Event | Data Direction | Architectural Treatment |
|---|---|---|
| `/pause` | TUI → CommandDispatch → graph interrupt | Freeze current graph run, persist pause event if a turn has started, show modal choices. Resume with LangGraph `Command(resume=...)`. |
| `/line` | TUI → SafetyGuard → Oracle reroute → Orator fade | Add `SafetyEvent(kind="line")`, update `ContentPolicy` if confirmed, reroute upcoming scene intent before more prose. |
| `/retcon` | TUI → command handler → PersistenceService → graph state update | Mark last completed turn retconned, apply inverse deltas if available, rebuild affected vault/indices, checkpoint new canonical state. Never let an agent silently retcon canon. |
| Late roll | Orator → structured `RollRequest` → graph interrupt/dice overlay → RulesLawyer → Orator resume | Orator may request a roll only at commit points. RulesLawyer/PF2e engine resolve; Orator narrates result after deterministic outcome. |

### Memory Retrieval Flow

```text
Scene context + player input
  → Archivist read node
  → exact search in SQLite FTS5
  → entity/callback lookup in master vault frontmatter
  → semantic lookup in LanceDB
  → topology query in NetworkX
  → rolling summary selection
  → rank/trim to token cap
  → MemoryPacket in SagaState
  → Oracle and Orator consume packet
```

The master vault is canonical; retrieval indices are acceleration/recall aids only. If indices disagree with vault files, rebuild the indices and trust vault + SQLite logs.

### Agent Skills Flow

```text
Graph node construction
  → SkillStore scans first-party skill directories
  → node receives skill catalog metadata in base prompt
  → LLM can call load_skill(name)
  → adapter loads SKILL.md body/resources
  → activation is logged for trace/eval
  → node emits schema-validated output
```

Skills are capability disclosure, not authority. Loading a PF2e skill can help a node propose an action, but only `services/rules/` can resolve the mechanics.

## State Ownership

SagaSmith should treat state as layered, with each layer having one authority.

| State / Artifact | Authoritative Owner | Mutable By | Read By | Notes |
|---|---|---|---|---|
| `SagaState.phase`, routing flags | LangGraph runtime | Graph routing nodes | All nodes | Compact orchestration state only. |
| `campaign_id`, `session_id`, `turn_id` | App/session manager + graph runtime | Bootstrap/session service | All components | IDs are stable and should be included in all logs. |
| `PlayerProfile`, `ContentPolicy`, `HouseRules` | SQLite campaign DB | Onboarding flow + settings commands | Oracle, Orator, SafetyGuard, CostGovernor | Validated before play; copied compactly into checkpoints. |
| LLM API key material | OS keyring/env | Provider config UI/CLI | Provider adapter only | Checkpoints and logs store key references, never values. |
| `CharacterSheet` | SQLite + checkpoint compact copy | Character creation and deterministic rules deltas | Rules engine, TUI, Orator | Rules engine validates legality. |
| `SessionState` | LangGraph checkpoint + SQLite turn records | Graph runtime and persistence service | Oracle, Archivist, TUI | Stores current scene, clock, quest refs, transcript cursor. |
| `CombatState` | Deterministic PF2e engine | Rules engine only | RulesLawyer, Orator, TUI | Non-null only during combat; LLMs cannot directly mutate. |
| `SceneBrief` | Oracle node | Oracle only, after SafetyGuard pre-gate | RulesLawyer, Orator, Archivist | Plan only; never player-facing narration. |
| `MemoryPacket` | Archivist read path | Archivist read node | Oracle, Orator | Token-bounded, rebuilt per relevant turn. Not canonical. |
| `CheckProposal` | RulesLawyer node / IntentResolver | RulesLawyer node | PF2e engine, dice overlay | Proposals require deterministic validation. |
| `RollResult`, `CheckResult` | DiceService + PF2e engine | Deterministic services only | Orator, TUI, persistence | Roll logs must reproduce with same seed/context. |
| `StateDelta(source="rules")` | PF2e engine | Rules engine | Persistence, graph reducers, eval replay | Must be serializable and replayable. |
| `StateDelta(source="oracle"/"archivist")` | Oracle/Archivist draft plus validation | Corresponding node after schema checks | Persistence, graph reducers | Cannot override mechanics without conflict path. |
| Transcript records | SQLite | PersistenceService | TUI, Archivist, evals | Stream buffer is noncanonical until turn close succeeds. |
| LLM call logs/cost logs | SQLite | LLM logging + CostGovernor | CostGovernor, evals, debug UI | Redacted by construction. |
| LangGraph checkpoints | SQLite checkpointer | Graph runtime through PersistenceService ordering | Resume/replay/evals | Compact state, schema/app-versioned. |
| Master vault | VaultStore under Archivist write path | Archivist via PersistenceService/VaultStore | Archivist retrieval, rebuild tools | Canonical campaign memory including GM-only content. |
| Player vault | PlayerVaultProjector | Projection service only | Player/Obsidian/TUI | Read-only artifact from app perspective; not canonical. |
| FTS5/LanceDB/NetworkX | Derived indexers | Rebuild/index services | Archivist retrieval | Always rebuildable from SQLite + master vault. |
| Safety events | SQLite + compact `SagaState` current turn | SafetyGuard/command handler | TUI, Oracle, Orator, evals | Required for visible safety audit. |
| CostState | CostGovernor + SQLite logs | CostGovernor only | Graph routing, TUI | Hard stop occurs before next paid LLM call. |

### Reducer Guidance for `SagaState`

Use explicit reducer behavior per field rather than relying on accidental dict overwrites:

- Append-only during turn: `check_results`, `state_deltas`, `safety_events`.
- Replace per turn: `pending_player_input`, `memory_packet`, `scene_brief`.
- Persist/carry across turns: `player_profile`, `content_policy`, `house_rules`, `character_sheet`, `session_state`, `combat_state`, `cost_state`.
- Clear after consumption: `pending_conflicts` after Oracle acknowledges them; transient dice/late-roll requests after resolution.

## Build Order

The safest build order is to construct the deterministic substrate first, then graph orchestration, then LLM nodes, then memory depth. This avoids building impressive agent behavior on top of untrusted persistence/rules boundaries.

### Phase 1 — Project Scaffold, Schemas, and Deterministic Foundation

**Build:**

1. Package scaffold with `uv`, `sagasmith` import package, CLI skeleton.
2. Pydantic models for first-slice `STATE_SCHEMA.md` objects.
3. JSON Schema export and validation helpers.
4. SQLite schema/migrations for campaign metadata, profiles, transcripts, roll logs, LLM logs, cost logs, checkpoints, state deltas.
5. Deterministic services: DiceService, CostGovernor, CommandDispatch, schema validation, atomic file write.
6. PF2e minimal rules engine for degree of success, seeded rolls, skill checks, strike, initiative, action economy, theater positioning.

**Dependency implications:** graph nodes and agents can be stubbed until schemas and deterministic services exist. Do not start prompt iteration before roll/replay fixtures pass.

**Testing/eval implications:**

- Unit tests for every Pydantic model round-trip and JSON Schema validation failure.
- Golden tests for PF2e degree boundaries, natural 1/20 adjustments, seeded replay.
- CostGovernor threshold tests: 70% and 90% once, hard-stop before paid call.
- Secret redaction tests for log rows.

### Phase 2 — Persistence Spine and Vault IO

**Build:**

1. PersistenceService with required turn-close ordering.
2. LangGraph SQLite checkpointer wiring.
3. Master vault page parser/writer with atomic replacement and YAML validation.
4. Player vault projection with GM-only stripping and wikilink/frontmatter validation.
5. Minimal `ttrpg vault rebuild` and `ttrpg vault sync` repair commands.

**Dependency implications:** this phase must precede real Archivist writes and multi-session play. The first graph can run with canned agent outputs once final checkpoint + transcript + vault write behavior is reliable.

**Testing/eval implications:**

- Crash injection after SQLite commit and before vault write/index sync.
- Atomic write tests that prove either old or new file exists, never partial.
- Player vault spoiler tests for `visibility: gm_only`, `foreshadowed`, `secrets`, `gm_*`, and `<!-- gm: -->` blocks.
- Rebuild tests from seed vault fixtures.

### Phase 3 — Graph Runtime Skeleton and Textual Event Bridge

**Build:**

1. `StateGraph[SagaState]` with stub nodes and phase routing.
2. Stream/update event normalization layer.
3. Textual app layout: transcript, status panel, input, dice overlay, safety bar.
4. Worker-based graph execution so streaming and long-running work do not block the UI.
5. Interrupt handling for `/pause`, `/line`, dice reveal, and basic `/save`, `/sheet`, `/clock`, `/budget` commands.

**Dependency implications:** Textual should consume neutral app events, not LangGraph internals. This makes headless evals possible and keeps UI replaceable later.

**Testing/eval implications:**

- Headless graph tests using canned input and stub nodes.
- Textual snapshot/smoke tests for screen layout where practical.
- Interrupt/resume tests for pause and dice reveal.
- Replay from checkpoint tests using LangGraph state history/checkpoints.

### Phase 4 — Provider Abstraction and Agent Skills Adapter

**Build:**

1. `LLMClient` protocol and OpenRouter implementation.
2. Structured JSON completion and streaming text call paths.
3. Retry policy and redacted LLM call logging.
4. Static pricing table fallback.
5. First-party SkillStore: scan directories, parse frontmatter, render catalog, expose `load_skill`, log activations.

**Dependency implications:** agents should be implemented only against `LLMClient`; provider-specific concerns must be invisible to prompts and graph nodes. Skill adapter can be small and first-party as ADR-0001 recommends.

**Testing/eval implications:**

- Mock provider tests for completion, stream chunks, usage updates, failures, retries.
- Schema repair tests for invalid structured JSON.
- Skill discovery/loading tests with malformed frontmatter and missing skills.
- Activation logs included in turn trace for future evals.

### Phase 5 — First Playable Agent Loop with Canned Memory

**Build:**

1. Onboarding node producing validated profile/policy/house rules.
2. Oracle `scene-brief-composition`, `player-choice-branching`, `content-policy-routing`, minimal `inline-npc-creation`.
3. RulesLawyer node wrapping deterministic services.
4. Orator streaming narration from `SceneBrief` + `CheckResult` + canned/minimal `MemoryPacket`.
5. Safety pre/post gates integrated before/after generation.
6. Turn-close persist node writing transcript, rolls, checkpoints, minimal vault updates.

**Dependency implications:** keep memory retrieval shallow at first; prove the full turn loop before adding LanceDB/NetworkX complexity. Oracle can use fixture world/seed content until vault-backed campaign generation is stable.

**Testing/eval implications:**

- MVP smoke: init → configure fake or real provider → onboarding → pregenerated PC → skill challenge → simple combat → save/resume.
- Rules contradiction eval: Orator output must not contradict `CheckResult`.
- Safety redline eval with post-gate rewrite/fallback.
- Budget hard-stop eval mid-session.

### Phase 6 — Full Archivist Memory and Derived Retrieval

**Build:**

1. MemoryPacket assembly from exact, semantic, graph, callback, and rolling-summary sources.
2. Entity resolution: slug → aliases → LanceDB similarity.
3. Canon conflict detection and Oracle conflict response.
4. Rolling summary updates.
5. Callback reachability and payoff selection.
6. Session page authoring.

**Dependency implications:** LanceDB and NetworkX can remain stubs until vault and FTS5 retrieval are useful. The vault must remain the source of truth; never let vector or graph output directly overwrite canon.

**Testing/eval implications:**

- 10-session recall fixture for early NPC reintroduction.
- Entity-resolution precision fixture target ≥ 0.95.
- MemoryPacket token cap tests.
- Canon conflict categorization fixtures.
- Callback seed-to-payoff fixture across multi-session transcript.

### Phase 7 — Hardening, Repair, and Release Evals

**Build:**

1. Schema migration/version handling for checkpoints and DB.
2. Robust retcon path with inverse deltas or safe manual stop.
3. Vault repair UX and stale-index detection.
4. Eval runner that can replay deterministic turns headlessly.
5. Release smoke suite and fixture docs.

**Dependency implications:** do not claim multi-session durability until repair commands and checkpoint migration behavior are tested.

**Testing/eval implications:**

- Deterministic replay of all non-LLM mechanics.
- Resume after failed Orator stream from pre-narration checkpoint.
- Retcon removes last completed turn from canon and rebuilds affected artifacts.
- End-to-end seed campaign run produces valid player vault with no spoilers.

## Integration Risks

### 1. Partial Canon Writes and Split-Brain Storage

**Risk:** SQLite says a turn completed, but master vault or derived indices did not update.  
**Why it matters:** memory recall and player vault projection can drift from transcript/roll history.  
**Mitigation:** enforce `PERSISTENCE_SPEC.md` ordering; mark `needs_vault_repair`; make rebuild/sync commands first-class; test crash points.  
**Phase flag:** Phase 2 and Phase 7 need deeper failure-mode testing.

### 2. LLM Agents Accidentally Owning Deterministic Decisions

**Risk:** Rules, costs, safety, or persistence decisions get embedded in prompts and become non-replayable.  
**Why it matters:** undermines auditability and can create rules contradictions.  
**Mitigation:** code-level boundaries: PF2e engine emits rules deltas, CostGovernor emits budget stops, PersistenceService writes, SafetyGuard gates. Agents may request, never decide final deterministic outcomes.  
**Phase flag:** Phase 5 prompt contracts and evals must explicitly check this.

### 3. Textual UI Blocking on Graph/Provider Calls

**Risk:** streaming or long provider calls freeze the terminal.  
**Why it matters:** breaks perceived responsiveness and safety controls.  
**Mitigation:** run graph execution in Textual workers; forward normalized stream/update events; use `call_from_thread` when thread workers are required; keep UI as subscriber.  
**Phase flag:** Phase 3 should spike streaming under artificial latency.

### 4. LangGraph Checkpoint Granularity Mismatch

**Risk:** checkpoint timing does not line up with SagaSmith's pre-narration and final turn-close semantics.  
**Why it matters:** resume after stream failure may replay too much or too little.  
**Mitigation:** define explicit pre-narration checkpoint after mechanics and before Orator stream; final checkpoint inside SQLite commit; use stable `thread_id` per campaign/session; add resume tests for final vs pre-narration checkpoints.  
**Phase flag:** Phase 3/5 integration spike.

### 5. Memory Packet Becomes a Context Dump

**Risk:** Archivist retrieves too much and defeats the Agent Skills/context-budget design.  
**Why it matters:** higher cost, slower first token, worse model focus.  
**Mitigation:** `MemoryPacket.token_cap` is mandatory; retrieval stages rank/trim; graph state carries references and compact summaries, not full vault pages.  
**Phase flag:** Phase 6 eval must measure token cap compliance.

### 6. Player Vault Spoilers

**Risk:** GM-only content leaks into files the player opens in Obsidian.  
**Why it matters:** violates a core product promise.  
**Mitigation:** projection-only writes; strip `secrets`, `gm_notes`, `gm_*`, and GM HTML blocks; skip `gm_only`; stub `foreshadowed`; run safety-redline and spoiler fixture tests before projection.  
**Phase flag:** Phase 2 and Phase 6.

### 7. Provider Abstraction Leaks into Agents

**Risk:** prompts or nodes assume OpenRouter-specific response fields or model features.  
**Why it matters:** breaks BYOK/direct-provider roadmap.  
**Mitigation:** agents use `LLMClient` only; structured output contract is SagaSmith-owned; log provider-specific metadata separately.  
**Phase flag:** Phase 4.

### 8. Agent Skills Overhead and Unbounded Activation

**Risk:** every node loads many skills every turn, increasing latency and cost.  
**Why it matters:** Orator first token target and budget enforcement suffer.  
**Mitigation:** inject only skill catalog metadata by default; inline only always-needed micro-instructions; log activations; add evals for activation count and prompt-token budgets.  
**Phase flag:** Phase 4/5.

### 9. Retcon Complexity Underestimated

**Risk:** `/retcon` cannot reliably reverse vault pages, indices, combat state, and summaries.  
**Why it matters:** unsafe canon mutation creates long-term memory corruption.  
**Mitigation:** store replayable state deltas and turn records from day one; first implementation can stop safely when inverse deltas are unavailable; full retcon hardening belongs after normal turn persistence is stable.  
**Phase flag:** Phase 7, with minimal safe behavior earlier.

### 10. Derived Indexes Treated as Canon

**Risk:** LanceDB similarity or NetworkX topology returns stale/wrong facts and updates vault pages.  
**Why it matters:** semantic retrieval errors become permanent canon errors.  
**Mitigation:** derived layers only suggest context; Archivist validates against master vault and emits `CanonConflict` instead of overwriting. Rebuild from vault is always possible.  
**Phase flag:** Phase 6.

## Testing and Eval Architecture

Testing should mirror component boundaries:

| Layer | Test Type | Examples |
|---|---|---|
| Schemas | Unit + property tests | Pydantic validation, JSON Schema export, checkpoint serialization, migration compatibility. |
| Deterministic services | Golden fixtures | PF2e degree math, seeded dice, strike/initiative/action economy, cost thresholds, command parsing. |
| Persistence | Crash/recovery tests | SQLite transaction rollback, checkpoint placement, atomic vault writes, rebuild/sync commands. |
| Graph | Headless integration tests | Route by phase, interrupt/resume, pre-narration resume, final checkpoint resume, safety/cost stops. |
| Providers | Mock contract tests | streaming chunks, usage events, retries, JSON repair, redaction. |
| Agents | Schema + behavioral evals | Oracle emits valid non-narrative SceneBrief; Orator never contradicts mechanics; Archivist detects conflicts. |
| Memory | Retrieval fixtures | token cap, early NPC recall, entity resolution precision, no duplicate pages, callback reachability. |
| TUI | Smoke/snapshot/manual harness | streaming display remains responsive, dice overlay interrupt, safety bar commands, repair warnings. |
| End-to-end | Seed campaign replay | init → onboarding → scene → skill check → combat → vault sync → quit/resume. |

**Key principle:** every graph run should produce a trace containing node order, skill activations, LLM call metadata, cost deltas, safety events, state deltas, roll logs, checkpoint IDs, and persistence reports. This trace is the common artifact for debugging, evals, and future regression replay.

## Sources

- HIGH confidence — Project requirements: `.planning/PROJECT.md`.
- HIGH confidence — Product behavior and MVP acceptance: `docs/sagasmith/GAME_SPEC.md`.
- HIGH confidence — LangGraph/Agent Skills decision and directory binding: `docs/sagasmith/ADR-0001-orchestration-and-skills.md`.
- HIGH confidence — Runtime state ownership and compact graph state: `docs/sagasmith/STATE_SCHEMA.md`.
- HIGH confidence — Persistence ordering, checkpoints, rebuild behavior: `docs/sagasmith/PERSISTENCE_SPEC.md`.
- HIGH confidence — Provider abstraction, streaming, cost, retry, secrets: `docs/sagasmith/LLM_PROVIDER_SPEC.md`.
- HIGH confidence — Vault source-of-truth, two-vault projection, derived layers: `docs/sagasmith/VAULT_SCHEMA.md`.
- HIGH confidence — Skill catalogs and service capabilities: `docs/sagasmith/agents/*.md`.
- HIGH confidence — Context7 LangGraph documentation: streaming with `messages`/`updates`, interrupts with `Command(resume=...)`, checkpoint-backed history/time travel.
- HIGH confidence — Context7 Textual documentation: workers for async/thread background tasks, streaming UI updates, and safe thread-to-UI updates with `call_from_thread`.
