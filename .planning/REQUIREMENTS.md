# Requirements: SagaSmith

**Defined:** 2026-04-26
**Core Value:** A solo player can start, play, quit, and resume an AI-run PF2e campaign where the story adapts to their choices while rules, memory, safety, cost, and persistence remain trustworthy.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Project Foundation

- [ ] **FOUND-01**: Developer can install project dependencies with `uv` using a committed `pyproject.toml` and lockfile.
- [ ] **FOUND-02**: Developer can run linting, formatting, type checking, and tests through documented project commands.
- [ ] **FOUND-03**: Developer can import the `sagasmith` package and run the CLI entry point from a local checkout.
- [ ] **FOUND-04**: Developer can run a smoke test suite that exercises the app without making paid LLM calls.
- [ ] **FOUND-05**: Project source layout separates graph orchestration, agents, deterministic services, storage, UI, provider clients, and skills.

### State and Schemas

- [x] **STATE-01**: System defines Pydantic models for `PlayerProfile`, `ContentPolicy`, `HouseRules`, `SagaState`, `SessionState`, and `CostState`.
- [x] **STATE-02**: System defines Pydantic models for `SceneBrief`, `MemoryPacket`, `CharacterSheet`, `CheckProposal`, `CheckResult`, `RollResult`, `StateDelta`, and `CanonConflict`.
- [x] **STATE-03**: System exports JSON Schema for models that cross an LLM boundary or are persisted as structured records.
- [x] **STATE-04**: System rejects invalid persisted state before it is consumed by downstream graph nodes.
- [x] **STATE-05**: System stores compact graph state references rather than full vault bodies or unbounded transcript history.

### CLI and Local Setup

- [x] **CLI-01**: User can run a first-time initialization command that creates a local campaign directory, SQLite campaign database, and player vault directory.
- [x] **CLI-02**: User can choose or confirm campaign name and local campaign path during initialization.
- [x] **CLI-03**: User can start or resume a campaign from the CLI without a hosted server.
- [ ] **CLI-04**: User can run repair commands for vault validation, player-vault sync, and derived-index rebuild.
- [x] **CLI-05**: User can run a demo or smoke mode that uses fixtures/mocks instead of paid provider calls.

### Provider, Secrets, and Cost

- [x] **PROV-01**: User can configure OpenRouter credentials by keyring reference or environment-variable reference without storing plaintext keys in campaign files.
- [x] **PROV-02**: System exposes a model-agnostic `LLMClient` protocol for non-streaming structured calls and streaming text calls.
- [x] **PROV-03**: System can make OpenRouter structured JSON calls and validate the returned payload against the requested schema.
- [x] **PROV-04**: System can stream narration tokens through the provider abstraction.
- [x] **PROV-05**: System logs LLM request/response metadata, failures, token usage, and cost estimates with secrets redacted.
- [x] **PROV-06**: User can configure default, narration, and cheap/fallback model names for a campaign.
- [x] **COST-01**: User can set a per-session budget during setup or onboarding.
- [x] **COST-02**: System updates `CostState` after every provider call using provider-reported or static-table pricing.
- [x] **COST-03**: System warns the user exactly once at 70% and 90% of the configured session budget.
- [x] **COST-04**: System hard-stops before making a paid LLM call that would exceed the configured session budget.
- [x] **COST-05**: User can inspect current cost and token usage with `/budget`.

### Onboarding and Player Contract

- [x] **ONBD-01**: User can complete onboarding that captures genre, tone, touchstones, pillar weights, pacing, combat style, dice UX, campaign length, character mode, death policy, and budget.
- [x] **ONBD-02**: User can define hard limits, soft limits, and content preferences during onboarding.
- [x] **ONBD-03**: User can review and edit onboarding outputs before they are committed.
- [x] **ONBD-04**: System persists validated `PlayerProfile`, `ContentPolicy`, and `HouseRules` before gameplay starts.
- [x] **ONBD-05**: User can re-run onboarding or adjust settings without deleting an existing campaign.

### Textual TUI and Commands

- [x] **TUI-01**: User sees a Textual interface with narration area, status panel, safety bar, and input line.
- [x] **TUI-02**: User can type natural-language actions into the input line during play.
- [x] **TUI-03**: User can scroll or review completed transcript entries during a session.
- [x] **TUI-04**: User sees HP, conditions, active quest, current location, in-game clock, and last rolls in the status panel.
- [x] **TUI-05**: User can open `/help` to view supported slash commands and descriptions.
- [x] **TUI-06**: User can use `/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/clock`, `/budget`, `/pause`, `/line`, `/retcon`, `/settings`, and `/help`.
- [x] **TUI-07**: User sees a dice overlay or equivalent modal for reveal-mode checks that shows DC, modifier, d20 result, total, and degree.
- [ ] **TUI-08**: User can quit from the TUI and resume later at the last safe prompt.

### Deterministic Rules and Dice

- [x] **RULE-01**: System computes PF2e degree of success from natural d20 value, total, and DC, including natural 1 and natural 20 adjustment rules.
- [x] **RULE-02**: System rolls dice through a seeded deterministic DiceService that records seed, inputs, natural value, modifier, total, DC, and timestamp.
- [x] **RULE-03**: System reproduces identical roll results when replaying the same seed and ordered roll inputs.
- [x] **RULE-04**: User can inspect one valid level-1 pregenerated martial `CharacterSheet` with `/sheet`.
- [x] **RULE-05**: System resolves a skill or Perception check against a fixed DC and emits a validated `CheckResult`.
- [x] **RULE-06**: System resolves Perception initiative and persists initiative order through checkpoints.
- [x] **RULE-07**: System resolves Strike actions against target AC and applies hit, miss, critical hit, damage, and HP state deltas.
- [x] **RULE-08**: System tracks three actions and one reaction per combatant per round in simple combat.
- [x] **RULE-09**: System applies theater-of-mind position tags `close`, `near`, `far`, and `behind_cover` for movement and targeting constraints.
- [x] **RULE-10**: User can complete one simple combat encounter with no more than two enemies.
- [x] **RULE-11**: System logs every mechanical check and roll in an auditable roll log.
- [x] **RULE-12**: System prevents LLM agents from directly inventing modifiers, DCs, damage, HP changes, action counts, or degree-of-success outcomes.

### Graph Runtime and Turn Flow

- [x] **GRAPH-01**: System constructs a LangGraph state graph with nodes or callable boundaries for onboarding, Oracle, RulesLawyer, Orator, Archivist, safety, cost, and persistence.
- [x] **GRAPH-02**: System checkpoints graph state after mechanics resolve and before Orator narration streams.
- [x] **GRAPH-03**: System checkpoints completed turn state during turn-close persistence.
- [x] **GRAPH-04**: System can interrupt the graph for `/pause`, `/line`, `/retcon`, budget hard-stop, and session end.
- [x] **GRAPH-05**: System resumes at the next prompt when the last turn has a final checkpoint.
- [ ] **GRAPH-06**: System can recover from an incomplete narration turn by rerunning narration or discarding the incomplete turn.
- [ ] **GRAPH-07**: System keeps deterministic rule outcomes stable even when LLM narration is retried.

### AI Agent Loop

- [x] **AI-01**: Oracle produces a validated `SceneBrief` with intent, beats, success outcomes, failure outcomes, present entities, pacing target, and relevant triggers.
- [x] **AI-02**: Oracle never emits direct player-facing narration.
- [x] **AI-03**: Oracle can produce 3-5 starting hooks or a curated first-slice hook aligned with onboarding preferences.
- [x] **AI-04**: Oracle can re-plan when the player accepts, rejects, bypasses, or reframes a planned beat.
- [ ] **AI-05**: Oracle can create small-scope NPC drafts for the active scene while preserving future consistency through Archivist records.
- [x] **AI-06**: RulesLawyer converts player intent and scene context into mechanical proposals without narrating outcomes.
- [ ] **AI-07**: Orator is the only player-facing narrative voice and renders scene plans, memory, player input, and resolved mechanics into second-person prose.
- [ ] **AI-08**: Orator streams at least one complete beat of narration for each completed turn.
- [ ] **AI-09**: Orator respects configured dice UX modes: auto, reveal, and hidden.
- [ ] **AI-10**: Orator does not contradict resolved mechanical outcomes in generated narration.
- [x] **AI-11**: Archivist assembles a token-bounded `MemoryPacket` for Oracle and Orator before scene planning or narration.
- [x] **AI-12**: System records which agent nodes and skills ran during a turn for audit and debugging.

### Agent Skills

- [x] **SKILL-01**: System can discover Agent Skills packages from configured skill directories.
- [x] **SKILL-02**: System can present each agent with a compact skill catalog containing skill name and description.
- [x] **SKILL-03**: System exposes a `load_skill` mechanism that returns the selected skill's full instructions/resources to the requesting agent.
- [x] **SKILL-04**: System logs skill activations per agent turn.
- [x] **SKILL-05**: System keeps first-slice agent behavior functional with only the required first-slice skill set loaded.

### Persistence and Vault Memory

- [x] **PERS-01**: System stores profiles, settings, transcripts, roll logs, turn records, checkpoints, cost logs, and applied state deltas in SQLite.
- [x] **PERS-02**: System performs turn-close SQLite writes in a transaction before writing vault files or derived indices.
- [x] **PERS-03**: System writes master-vault pages with atomic file replacement and validates YAML frontmatter after write.
- [x] **PERS-04**: System marks a turn complete only after turn-close persistence succeeds.
- [ ] **PERS-05**: System surfaces a repair warning when player-vault sync or derived-index updates fail after a completed turn.
- [ ] **PERS-06**: System can rebuild derived indices from SQLite plus master vault after corruption or deletion.
- [x] **VAULT-01**: System creates a master vault in app data and a player vault in the campaign directory.
- [x] **VAULT-02**: System writes Obsidian-compatible markdown pages with YAML frontmatter and wikilinks for sessions, NPCs, locations, factions, items, quests, callbacks, lore, index, and log.
- [ ] **VAULT-03**: System enforces `gm_only`, `foreshadowed`, and `player_known` visibility states when projecting the player vault.
- [ ] **VAULT-04**: System strips GM-only frontmatter fields and `<!-- gm: ... -->` blocks from player-vault projections.
- [ ] **VAULT-05**: System generates or refreshes player-vault `index.md` and `log.md` after sync.
- [x] **VAULT-06**: System resolves incoming named entities by slug and aliases before creating a new vault page.
- [ ] **VAULT-07**: System can assemble memory from exact search, graph neighborhoods, callbacks, summaries, and semantic retrieval interfaces without exceeding the configured token cap.
- [ ] **VAULT-08**: System detects canon conflicts and surfaces them rather than silently overwriting canonical facts.
- [ ] **VAULT-09**: User can run `/recap` to receive a summary based on persisted transcript and canonical memory.
- [ ] **VAULT-10**: User can resume a campaign after a later process start and see NPCs, quests, and prior events recalled correctly.

### Safety and Control

- [ ] **SAFE-01**: System blocks or reroutes scene intents that violate configured hard limits before generation.
- [ ] **SAFE-02**: System fades, avoids detail, or asks first for soft-limit content according to `ContentPolicy`.
- [ ] **SAFE-03**: System scans player-facing generated prose and retries or falls back when generated content violates policy.
- [x] **SAFE-04**: User can invoke `/pause` to freeze play and choose to continue, retcon, or adjust lines.
- [x] **SAFE-05**: User can invoke `/line` mid-scene and see subsequent narration rerouted or faded away from the redlined content.
- [x] **SAFE-06**: System logs safety events without exposing secrets or GM-only spoilers in the player vault.

### Retcon, Repair, and Quality Gates

- [ ] **QA-01**: User can retcon the last completed turn after confirmation for simple state and vault changes.
- [ ] **QA-02**: System excludes retconned turns from canonical replay, summaries, and vault rebuilds.
- [x] **QA-03**: Test suite covers PF2e degree boundaries, natural 1/20 adjustment, seeded replay, skill checks, Strike, initiative, HP damage, and roll log completeness.
- [x] **QA-04**: Test suite verifies API keys and auth headers never appear in logs, vaults, transcripts, checkpoints, or generated artifacts.
- [ ] **QA-05**: Test suite verifies configured hard-limit content does not appear in player-facing prose across a regression scenario.
- [ ] **QA-06**: Test suite verifies player-vault projection contains no GM-only fields, comments, or pages.
- [x] **QA-07**: Test suite verifies CostGovernor warnings and hard-stop behavior.
- [ ] **QA-08**: Smoke suite verifies install/init/configure/onboard/play skill challenge/play simple combat/quit/resume without paid LLM calls.
- [ ] **QA-09**: Release gate requires lint, type check, unit tests, smoke tests, and secret scan to pass.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Character and Rules Expansion

- **CHAR-01**: User can create a character through a guided PF2e character creation wizard.
- **CHAR-02**: User can describe a character in prose and receive a legal editable character sheet proposal.
- **RULEX-01**: System supports PF2e spellcasting with curated spell list, saving throws, durations, and resources.
- **RULEX-02**: System supports PF2e levels 1-3 beyond the first-slice level-1 martial pregen.
- **RULEX-03**: System validates encounter XP budgets for levels 1-3.
- **RULEX-04**: System supports additional PF2e actions: Raise a Shield, Demoralize, Recall Knowledge, Trip, Grapple, and Cast a Spell.
- **RULEX-05**: System supports conditions: frightened, off-guard, prone, dying, wounded, and drained.

### Campaign and Memory Expansion

- **MEMX-01**: User can unlock the master vault after campaign end as a director's-cut artifact.
- **MEMX-02**: Archivist can tune LanceDB semantic entity resolution against a labeled fixture suite.
- **MEMX-03**: Oracle can maintain a callback ledger that proves at least one seed-to-payoff cycle in a 5-session campaign.
- **MEMX-04**: System can migrate old checkpoints and campaign databases across app versions.

### Experience Expansion

- **EXPX-01**: User can use richer dice animations and themeable dice visuals.
- **EXPX-02**: User can open a GUI/web frontend backed by the local game runtime.
- **EXPX-03**: User can use voice input and/or text-to-speech narration.
- **EXPX-04**: User can use Director Mode to override Oracle scene plans.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multiplayer or LAN/shared campaigns | Requires network synchronization, multi-PC mechanics, conflict resolution, and cost allocation beyond MVP. |
| Party companions / multi-PC support | Adds multi-character state, combat balance, companion agency, and relationship systems before solo loop is proven. |
| Tactical grid or map-based combat | High-complexity VTT problem; MVP validates theater-of-mind combat only. |
| AI-generated art pipeline | Cost, latency, consistency, storage, and safety concerns do not support first terminal MVP. |
| Standalone CartographerAgent | Textual spatial notes and abstract position tags are sufficient for MVP. |
| Standalone PuppeteerAgent | Oracle can generate small-scope NPCs inline for a small MVP world. |
| Standalone VillainAgent | Persistent adversary planning needs separate memory, evals, and authority negotiation after core loop works. |
| PF2e levels 4+ | Data volume and progression complexity are unnecessary for initial validation. |
| Multiple rules systems | Each system requires its own data, engine behavior, tests, and UX. |
| Custom/homebrew rule-system builder | Requires a rules DSL/interpreter and is a long-term platform feature. |
| Hosted account system or cloud sync | Contradicts local-first MVP and introduces operational burden. |
| Public campaign sharing, marketplace, or scripting platform | Requires hosting, moderation, security sandboxing, and authoring tools. |
| Dedicated graph database as source of truth | Vault remains canonical; graph stores are derived and rebuildable only. |
| Player edits to vault as canonical state | Creates source-of-truth ambiguity; canon changes go through game commands. |
| Exposing master vault during active campaign | Spoils GM-only planning and undermines solo-GM illusion. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| FOUND-05 | Phase 1 | Complete |
| STATE-01 | Phase 1 | Complete |
| STATE-02 | Phase 1 | Complete |
| STATE-03 | Phase 1 | Complete |
| STATE-04 | Phase 1 | Complete |
| STATE-05 | Phase 1 | Complete |
| PROV-01 | Phase 2 | Complete |
| PROV-02 | Phase 2 | Complete |
| PROV-03 | Phase 2 | Complete |
| PROV-04 | Phase 2 | Complete |
| PROV-05 | Phase 2 | Complete |
| PROV-06 | Phase 2 | Complete |
| COST-01 | Phase 2 | Complete |
| COST-02 | Phase 2 | Complete |
| COST-03 | Phase 2 | Complete |
| COST-04 | Phase 2 | Complete |
| COST-05 | Phase 2 | Complete |
| RULE-01 | Phase 2 | Complete |
| RULE-02 | Phase 2 | Complete |
| RULE-03 | Phase 2 | Complete |
| PERS-01 | Phase 2 | Complete |
| PERS-02 | Phase 2 | Complete |
| PERS-04 | Phase 2 | Complete |
| QA-04 | Phase 2 | Complete |
| QA-07 | Phase 2 | Complete |
| CLI-01 | Phase 3 | Complete |
| CLI-02 | Phase 3 | Complete |
| CLI-03 | Phase 3 | Complete |
| CLI-05 | Phase 3 | Complete |
| ONBD-01 | Phase 3 | Pending |
| ONBD-02 | Phase 3 | Pending |
| ONBD-03 | Phase 3 | Pending |
| ONBD-04 | Phase 3 | Pending |
| ONBD-05 | Phase 3 | Pending |
| TUI-01 | Phase 3 | Complete |
| TUI-02 | Phase 3 | Complete |
| TUI-03 | Phase 3 | Complete |
| TUI-04 | Phase 3 | Complete |
| TUI-05 | Phase 3 | Complete |
| TUI-06 | Phase 3 | Complete |
| SAFE-04 | Phase 3 | Complete |
| SAFE-05 | Phase 3 | Complete |
| SAFE-06 | Phase 3 | Complete |
| GRAPH-01 | Phase 4 | Complete |
| GRAPH-02 | Phase 4 | Complete |
| GRAPH-03 | Phase 4 | Complete |
| GRAPH-04 | Phase 4 | Complete |
| GRAPH-05 | Phase 4 | Complete |
| AI-12 | Phase 4 | Complete |
| SKILL-01 | Phase 4 | Complete |
| SKILL-02 | Phase 4 | Complete |
| SKILL-03 | Phase 4 | Complete |
| SKILL-04 | Phase 4 | Complete |
| SKILL-05 | Phase 4 | Complete |
| RULE-04 | Phase 5 | Complete |
| RULE-05 | Phase 5 | Complete |
| RULE-06 | Phase 5 | Complete |
| RULE-07 | Phase 5 | Complete |
| RULE-08 | Phase 5 | Complete |
| RULE-09 | Phase 5 | Complete |
| RULE-10 | Phase 5 | Complete |
| RULE-11 | Phase 5 | Complete |
| RULE-12 | Phase 5 | Complete |
| TUI-07 | Phase 5 | Complete |
| QA-03 | Phase 5 | Complete |
| AI-01 | Phase 6 | Complete |
| AI-02 | Phase 6 | Complete |
| AI-03 | Phase 6 | Complete |
| AI-04 | Phase 6 | Complete |
| AI-05 | Phase 6 | Pending |
| AI-06 | Phase 6 | Complete |
| AI-07 | Phase 6 | Pending |
| AI-08 | Phase 6 | Pending |
| AI-09 | Phase 6 | Pending |
| AI-10 | Phase 6 | Pending |
| GRAPH-06 | Phase 6 | Pending |
| GRAPH-07 | Phase 6 | Pending |
| SAFE-01 | Phase 6 | Pending |
| SAFE-02 | Phase 6 | Pending |
| SAFE-03 | Phase 6 | Pending |
| QA-05 | Phase 6 | Pending |
| CLI-04 | Phase 7 | Pending |
| PERS-03 | Phase 7 | Complete |
| PERS-05 | Phase 7 | Pending |
| PERS-06 | Phase 7 | Pending |
| VAULT-01 | Phase 7 | Complete |
| VAULT-02 | Phase 7 | Complete |
| VAULT-03 | Phase 7 | Pending |
| VAULT-04 | Phase 7 | Pending |
| VAULT-05 | Phase 7 | Pending |
| VAULT-06 | Phase 7 | Complete |
| VAULT-07 | Phase 7 | Pending |
| VAULT-08 | Phase 7 | Pending |
| VAULT-09 | Phase 7 | Pending |
| VAULT-10 | Phase 7 | Pending |
| AI-11 | Phase 7 | Complete |
| TUI-08 | Phase 7 | Pending |
| QA-06 | Phase 7 | Pending |
| QA-01 | Phase 8 | Pending |
| QA-02 | Phase 8 | Pending |
| QA-08 | Phase 8 | Pending |
| QA-09 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 106 total
- Mapped to phases: 106
- Unmapped: 0
- Duplicate mappings: 0

**Count note:** The initial coverage footer listed 119 v1 requirements, but the v1 section contains 106 unique requirement IDs. All 106 discovered v1 IDs are mapped exactly once above.

---
*Requirements defined: 2026-04-26*
*Last updated: 2026-04-28 after Phase 6 Plan 06-02 completion*
