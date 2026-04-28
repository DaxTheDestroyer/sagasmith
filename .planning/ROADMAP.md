# Roadmap: SagaSmith

## Overview

SagaSmith v1 follows a trust-before-breadth path: establish the local Python package, typed contracts, deterministic services, provider/cost/safety boundaries, and persistence spine before turning on AI gameplay. The roadmap then exposes those foundations through CLI/TUI setup and onboarding, wires LangGraph and Agent Skills, proves a narrow PF2e rules-first slice, adds the AI GM story loop, delivers spoiler-safe persistent memory, and finishes with retcon, repair, and release gates. This preserves the research-recommended build order while keeping every v1 requirement mapped to exactly one phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Contracts, Scaffold, and Eval Spine** - Developer can run a local package skeleton with typed state contracts and schema/eval guardrails. (completed 2026-04-26)
- [x] **Phase 2: Deterministic Trust Services** - Rules math, provider/cost handling, SQLite turn records, and privacy checks exist before paid gameplay. (completed 2026-04-26)
- [x] **Phase 3: CLI Setup, Onboarding, and TUI Controls** - User can create/configure a campaign, complete the player contract, and see responsive play controls. (completed 2026-04-27)
- [x] **Phase 4: Graph Runtime and Agent Skills** - LangGraph coordinates compact state, checkpoints, interrupts, and progressive skill disclosure. (completed 2026-04-27)
- [x] **Phase 5: Rules-First PF2e Vertical Slice** - User can inspect a pregen PC and complete deterministic skill/combat mechanics with auditable rolls. (completed 2026-04-28)
- [x] **Phase 6: AI GM Story Loop** - User can play AI-planned, AI-narrated turns while rules, safety, cost, and narration boundaries hold. (completed 2026-04-28)
- [ ] **Phase 7: Memory, Vault, and Resume Differentiator** - User gets durable spoiler-safe campaign memory, repairable vaults, recap, and later-process resume.
- [ ] **Phase 8: Retcon, Repair, and Release Hardening** - User can safely retcon the last turn and the release gate proves the MVP smoke flow.

## Phase Summary

| Phase | Name | Goal | Requirement IDs | Success Criteria | UI hint |
|-------|------|------|-----------------|------------------|---------|
| 1 | Contracts, Scaffold, and Eval Spine | Developer can run a local package skeleton with typed state contracts and schema/eval guardrails | FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, STATE-01, STATE-02, STATE-03, STATE-04, STATE-05 | 4 | no |
| 2 | Deterministic Trust Services | Provider, cost, rules primitives, persistence records, and privacy gates are deterministic and testable before gameplay | PROV-01, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, COST-01, COST-02, COST-03, COST-04, COST-05, RULE-01, RULE-02, RULE-03, PERS-01, PERS-02, PERS-04, QA-04, QA-07 | 5 | no |
| 3 | CLI Setup, Onboarding, and TUI Controls | User can initialize a local campaign, complete onboarding, and use responsive control commands in the Textual shell | CLI-01, CLI-02, CLI-03, CLI-05, ONBD-01, ONBD-02, ONBD-03, ONBD-04, ONBD-05, TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, SAFE-04, SAFE-05, SAFE-06 | 5 | yes |
| 4 | Graph Runtime and Agent Skills | LangGraph can route typed gameplay state through nodes, checkpoints, interrupts, and first-party skills | GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, AI-12, SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05 | 4 | no |
| 5 | Rules-First PF2e Vertical Slice | User can complete first-slice PF2e mechanics with a visible character sheet, dice overlay, replayable rolls, and no LLM-authored math | RULE-04, RULE-05, RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12, TUI-07, QA-03 | 4 | yes |
| 6 | AI GM Story Loop | User can play AI-planned and AI-narrated turns with Oracle, RulesLawyer, Orator, safety gates, and narration recovery | AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, AI-07, AI-08, AI-09, AI-10, GRAPH-06, GRAPH-07, SAFE-01, SAFE-02, SAFE-03, QA-05 | 5 | no |
| 7 | Memory, Vault, and Resume Differentiator | User gets persistent campaign memory, spoiler-safe Obsidian vault projection, recap, repair commands, and later-process resume | CLI-04, PERS-03, PERS-05, PERS-06, VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-05, VAULT-06, VAULT-07, VAULT-08, VAULT-09, VAULT-10, AI-11, TUI-08, QA-06 | 5 | no |
| 8 | Retcon, Repair, and Release Hardening | User can safely retcon the last completed turn and the MVP is protected by full smoke/release gates | QA-01, QA-02, QA-08, QA-09 | 3 | no |

## Phase Details

### Phase 1: Contracts, Scaffold, and Eval Spine
**Goal**: Developer can run a local package skeleton with typed state contracts and schema/eval guardrails
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, STATE-01, STATE-02, STATE-03, STATE-04, STATE-05
**Success Criteria** (what must be TRUE):
  1. Developer can install dependencies with `uv`, import `sagasmith`, and run the CLI entry point from a local checkout.
  2. Developer can run linting, formatting, type checking, tests, and a no-paid-call smoke suite through documented commands.
  3. Developer can validate and export JSON Schema for all first-slice persisted or LLM-bound Pydantic models.
  4. Invalid persisted state is rejected before graph nodes consume it, and compact graph state references avoid unbounded vault or transcript payloads.
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — Scaffold the `sagasmith` package with `uv`, subpackage layout, ruff/pyright/pre-commit/gitleaks config, Makefile commands, Typer CLI `version`, and developer run-book (FOUND-01, FOUND-02, FOUND-03, FOUND-05).
- [x] 01-02-PLAN.md — Implement Pydantic v2 state contracts, persisted-state validation gate, and `sagasmith schema export` CLI emitting JSON Schema for the 16 LLM-boundary/persisted models (STATE-01, STATE-02, STATE-03, STATE-04, STATE-05).
- [x] 01-03-PLAN.md — Build the no-paid-call eval/smoke spine: fixtures, redaction canary, round-trip helpers, in-process `run_smoke()` harness, and `sagasmith smoke` CLI (FOUND-04, plus end-to-end wiring for STATE-03/04/05).

### Phase 2: Deterministic Trust Services
**Goal**: Provider, cost, rules primitives, persistence records, and privacy gates are deterministic and testable before gameplay
**Depends on**: Phase 1
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, COST-01, COST-02, COST-03, COST-04, COST-05, RULE-01, RULE-02, RULE-03, PERS-01, PERS-02, PERS-04, QA-04, QA-07
**Success Criteria** (what must be TRUE):
  1. User can configure OpenRouter by keyring or environment-variable reference while campaign files, logs, transcripts, checkpoints, and vaults remain free of plaintext secrets.
  2. Developer can make mocked structured and streaming provider calls through a model-agnostic `LLMClient`, with schema validation, redacted metadata, usage, and cost logs.
  3. User can set and inspect a session budget, receive exactly one 70% and 90% warning, and be hard-stopped before an over-budget paid call.
  4. Developer can reproduce seeded d20 rolls and PF2e degree-of-success outcomes from the same ordered inputs.
  5. Completed-turn records, roll logs, state deltas, cost logs, and SQLite transaction ordering exist before any turn is marked complete.
**Plans**: 6 plans
Plans:
- [x] 02-01-PLAN.md — Typed trust-service errors, SecretRef (keyring/env) resolver, RedactionCanary `sk-proj-` coverage, HP invariant, and fixture override revalidation (PROV-01, QA-04, D-05/D-06/D-08/D-16).
- [x] 02-02-PLAN.md — DiceService with seeded deterministic replay and pure `compute_degree` PF2e degree-of-success math (RULE-01, RULE-02, RULE-03, D-13/D-14).
- [x] 02-03-PLAN.md — `LLMClient` protocol, typed request/response/stream/config models, D-03 retry ladder, metadata-only provider logs, and `DeterministicFakeClient` (PROV-02, PROV-03, PROV-04, PROV-05, PROV-06).
- [x] 02-04-PLAN.md — `CostGovernor` with static pricing table, exactly-once 70/90 warnings, pre-call worst-case budget block, and `BudgetInspection` data layer (COST-01, COST-02, COST-03, COST-04, COST-05, QA-07).
- [x] 02-05-PLAN.md — `OpenRouterClient` over injected `HttpTransport`, opt-in live verification, secret-free error paths (PROV-01, PROV-03, PROV-04).
- [x] 02-06-PLAN.md — SQLite trust-records schema v1, typed repositories, and atomic `close_turn` transaction with redaction sweep (PERS-01, PERS-02, PERS-04, QA-04).

### Phase 3: CLI Setup, Onboarding, and TUI Controls
**Goal**: User can initialize a local campaign, complete onboarding, and use responsive control commands in the Textual shell
**Depends on**: Phase 2
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-05, ONBD-01, ONBD-02, ONBD-03, ONBD-04, ONBD-05, TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, SAFE-04, SAFE-05, SAFE-06
**Success Criteria** (what must be TRUE):
  1. User can run first-time setup, choose or confirm campaign name/path, create local campaign storage, and start or resume without a hosted server.
  2. User can complete onboarding for story preferences, content policy, house rules, budget, dice UX, campaign length, and character mode, then review/edit before commit.
  3. User sees a Textual interface with narration area, status panel, safety bar, input line, scrollback, and supported slash-command help.
  4. User can type natural-language actions and use `/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/clock`, `/budget`, `/pause`, `/line`, `/retcon`, `/settings`, and `/help` command entries.
  5. User can invoke `/pause` or `/line` during play setup/control states and see a persisted, player-visible safety event without exposing secrets or GM-only spoilers.
**Plans**: 4 plans
Plans:
- [x] 03-01-PLAN.md — Campaign lifecycle + CLI shell: v2 migration (campaigns, settings), `sagasmith.app` subpackage, four Typer commands (init/play/configure/demo), CampaignManifest on disk (CLI-01, CLI-02, CLI-03, CLI-05).
- [x] 03-02-PLAN.md — Onboarding wizard domain + SQLite store: 9-phase state machine producing validated PlayerProfile/ContentPolicy/HouseRules, migration 0003 with three onboarding tables, atomic commit + re-run support (ONBD-01, ONBD-02, ONBD-03, ONBD-04, ONBD-05).
- [x] 03-03-PLAN.md — Textual TUI shell + CommandRegistry + `/help`: four named widgets (narration, status, safety bar, input), pilot-tested mount, SQLite-backed scrollback, `sagasmith play` upgraded to launch Textual (TUI-01, TUI-02, TUI-03, TUI-04, TUI-05).
- [x] 03-04-PLAN.md — Eleven control/safety/settings commands + `safety_events` migration: `/pause`, `/line`, `/budget`, `/settings` wired; `/save`/`/recap`/`/sheet`/`/inventory`/`/map`/`/retcon` stubs named for their owning future phase (TUI-06, SAFE-04, SAFE-05, SAFE-06).
**UI hint**: yes

### Phase 4: Graph Runtime and Agent Skills
**Goal**: LangGraph can route typed gameplay state through nodes, checkpoints, interrupts, and first-party skills
**Depends on**: Phase 3
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, AI-12, SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05
**Success Criteria** (what must be TRUE):
  1. Developer can run a LangGraph state graph with callable boundaries for onboarding, Oracle, RulesLawyer, Orator, Archivist, safety, cost, and persistence.
  2. The graph checkpoints after mechanics resolution, checkpoints completed turns during turn-close, and resumes at the next prompt after a final checkpoint.
  3. `/pause`, `/line`, `/retcon`, budget hard-stop, and session end are represented as graph interrupts or routing states rather than ad hoc UI behavior.
  4. Developer can discover skills, present compact catalogs, load full skill instructions on demand, and inspect per-turn agent/skill activation logs.
**Plans**: 5 plans (revised 2026-04-27 via `/gsd-plan-phase 4 --reviews` after cross-AI review feedback; originally 3 plans, split for task-size and LangGraph-native-interrupt concerns)
Plans:
- [x] 04-01-PLAN.md — LangGraph runtime foundation: add langgraph + langgraph-checkpoint-sqlite deps, typed StateGraph over SagaState, five thin agent node stubs (onboarding/oracle/rules_lawyer/orator/archivist), phase-driven routing with combat deferred to Phase 5, pending_narration field hoisted to Task 1 (GRAPH-01).
- [x] 04-02-PLAN.md — LangGraph integration spike + persistent graph: prove interrupt_before / checkpoint_id / thread_id semantics, then SqliteSaver-backed GraphRuntime with pre-narration + final CheckpointRef ownership at the runtime boundary (not inside nodes), agent_skill_log migration 0005 + AgentActivationLogger with contextvar (GRAPH-02, GRAPH-03, GRAPH-05, AI-12).
- [x] 04-03-PLAN.md — Native LangGraph interrupts + TUI command wiring + end-to-end smoke test: InterruptKind envelopes via update_state + Command(resume), /pause and /line dual-write SafetyEvents + interrupts, BudgetStopError translation at runtime boundary, RetconCommand deferred to Phase 8, tests/integration/test_tui_graph_smoke.py (GRAPH-04).
- [x] 04-04-PLAN.md — Skills adapter package: YAML-lite frontmatter parser, SkillStore with first_slice field + deterministic path sort + agent-scoped `["*"]` rejection, SkillCatalog, load_skill, errors hierarchy, pyproject.toml package-data config for SKILL.md files (SKILL-01, SKILL-02, SKILL-03, SKILL-05 mechanism).
- [x] 04-05-PLAN.md — First-slice SKILL.md catalog (13 first_slice + 1 future-scoped = 14 files across 5 agents + 3 cross-cutting) + node wiring via contextvar handoff (set_skill calls in every agent node), bootstrap helper that raises loud on production scan errors, end-to-end first_slice_only=True play turn proof (SKILL-04, SKILL-05 end-to-end).

### Phase 5: Rules-First PF2e Vertical Slice
**Goal**: User can complete first-slice PF2e mechanics with a visible character sheet, dice overlay, replayable rolls, and no LLM-authored math
**Depends on**: Phase 4
**Requirements**: RULE-04, RULE-05, RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12, TUI-07, QA-03
**Success Criteria** (what must be TRUE):
  1. User can inspect a valid level-1 pregenerated martial character sheet with `/sheet`.
  2. User can complete a skill or Perception check, see reveal-mode dice details when configured, and audit the roll log afterward.
  3. User can complete a simple theater-of-mind combat with initiative, action economy, position tags, Strikes, HP deltas, and no more than two enemies.
  4. Developer can run rules tests for PF2e degree boundaries, natural 1/20 adjustment, seeded replay, skill checks, Strike, initiative, HP damage, and roll log completeness.
**Plans**: 5 plans (revised 2026-04-27 via `/gsd-plan-phase 5 --reviews` to address cross-AI review feedback on damage auditability, parser/error UX, live sheet state, reveal behavior, combat edge cases, and QA-03 behavior coverage)
Plans:
- [x] 05-01-PLAN.md — Build deterministic first-slice pregen/enemy data and skill/Perception check resolution with auditable roll outputs (RULE-04, RULE-05, RULE-11, RULE-12, QA-03).
- [x] 05-02-PLAN.md — Implement first-slice combat engine for initiative, action economy, positions, Strikes, HP deltas, and encounter completion (RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12, QA-03).
- [x] 05-03-PLAN.md — Wire deterministic RulesLawyer graph behavior and combat routing so play/combat inputs use rules services, not LLM-authored math (RULE-05 through RULE-12).
- [x] 05-04-PLAN.md — Replace TUI stubs with `/sheet`, reveal-mode dice detail rendering, and combat-aware status output (RULE-04, RULE-06 through RULE-11, TUI-07).
- [x] 05-05-PLAN.md — Add no-paid-call vertical-slice integration and QA-03 verification gates for sheet, checks, reveal audit, and simple combat (RULE-04 through RULE-12, TUI-07, QA-03).
**UI hint**: yes

### Phase 6: AI GM Story Loop
**Goal**: User can play AI-planned and AI-narrated turns with Oracle, RulesLawyer, Orator, safety gates, and narration recovery
**Depends on**: Phase 5
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, AI-07, AI-08, AI-09, AI-10, GRAPH-06, GRAPH-07, SAFE-01, SAFE-02, SAFE-03, QA-05
**Success Criteria** (what must be TRUE):
  1. User can receive 3-5 starting hooks or a curated first-slice hook aligned with onboarding preferences.
  2. Oracle produces validated scene plans and replans around player choices without emitting player-facing narration.
  3. RulesLawyer converts player intent into deterministic mechanical proposals/results without letting LLMs invent modifiers, DCs, damage, HP, action counts, or degrees.
  4. Orator is the only player-facing narrative voice, streams at least one complete beat per completed turn, respects dice UX, and does not contradict resolved mechanics.
  5. Unsafe scene intents or generated prose are blocked, rerouted, retried, or safely degraded, and incomplete narration can be retried or discarded without changing deterministic outcomes.
**Plans**: 8 plans
Plans:
- [x] 06-01-PLAN.md — Implement World Bible and Campaign Seed Generation (Oracle).
- [x] 06-02-PLAN.md — Implement Scene Brief Composition (Oracle).
- [x] 06-03-PLAN.md — Implement Intent-to-Proposal Layer (RulesLawyer).
- [ ] 06-04-PLAN.md — Implement Scene Rendering with Safety Gates (Orator).
- [x] 06-05-PLAN.md — Implement Memory Packet Stub Assembly (Archivist).
- [ ] 06-06-PLAN.md — Implement Narration Discard + Recovery Commands (Graph + TUI).
- [ ] 06-07-PLAN.md — Implement Safety Event Logging and Testing (Safety).
- [ ] 06-08-PLAN.md — Integration Testing and Quality Assurance.

### Phase 7: Memory, Vault, and Resume Differentiator
**Goal**: User gets persistent campaign memory, spoiler-safe Obsidian vault projection, recap, repair commands, and later-process resume
**Depends on**: Phase 6
**Requirements**: CLI-04, PERS-03, PERS-05, PERS-06, VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-05, VAULT-06, VAULT-07, VAULT-08, VAULT-09, VAULT-10, AI-11, TUI-08, QA-06
**Success Criteria** (what must be TRUE):
  1. User can open a player vault containing Obsidian-compatible sessions, NPCs, locations, factions, items, quests, callbacks, lore, index, and log pages with no GM-only leakage.
  2. The system atomically writes validated master-vault pages, projects `player_known` and `foreshadowed` content safely, and strips GM-only frontmatter and comments from player projections.
  3. Archivist can resolve named entities, detect canon conflicts, and assemble bounded MemoryPackets from permitted search/retrieval sources.
  4. User can run `/recap`, quit from the TUI, resume after a later process start, and see prior NPCs, quests, events, and transcript context recalled correctly.
  5. User can run vault validation, player-vault sync, and derived-index rebuild commands when repair warnings or corruption are detected.
**Plans**: 6 plans
Plans:
- [ ] 07-01-PLAN.md — Vault foundation, atomic writes, entity resolution (VAULT-01, VAULT-02, VAULT-06, PERS-03, AI-11)
- [ ] 07-02-PLAN.md — Vault-page-upsert & turn-close persistence (VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-06, PERS-03, PERS-05, PERS-06, D-09)
- [ ] 07-03-PLAN.md — Full memory-packet assembly with FTS5 & NetworkX (VAULT-07, AI-11, PERS-06)
- [ ] 07-04-PLAN.md — Additional skills: visibility-promotion, rolling-summary-update, session-page-authoring, canon-conflict stub (VAULT-03, VAULT-05, VAULT-08, AI-11)
- [ ] 07-05-PLAN.md — Player-vault sync, CLI repair commands, /recap, quit/resume integration (CLI-04, VAULT-03, VAULT-04, VAULT-05, VAULT-09, VAULT-10, TUI-08, PERS-05)
- [ ] 07-06-PLAN.md — QA tests and release gate (QA-06, QA-08, QA-09)

### Phase 8: Retcon, Repair, and Release Hardening
**Goal**: User can safely retcon the last completed turn and the MVP is protected by full smoke/release gates
**Depends on**: Phase 7
**Requirements**: QA-01, QA-02, QA-08, QA-09
**Success Criteria** (what must be TRUE):
  1. User can retcon the last completed turn after confirmation, and retconned turns are excluded from canonical replay, summaries, and vault rebuilds.
  2. Developer can run the no-paid-call smoke suite for install, init, configure, onboard, play skill challenge, play simple combat, quit, and resume.
  3. Release is blocked unless lint, type check, unit tests, smoke tests, and secret scan pass.
**Plans**: TBD

## Coverage

Every v1 requirement ID present in `.planning/REQUIREMENTS.md` is mapped to exactly one phase.

| Metric | Count |
|--------|-------|
| v1 requirement IDs found | 106 |
| Mapped to phases | 106 |
| Unmapped | 0 |
| Duplicate mappings | 0 |

**Coverage note:** `.planning/REQUIREMENTS.md` previously listed 119 total v1 requirements in its coverage footer, but the v1 section contains 106 unique requirement IDs. This roadmap maps all 106 discovered IDs and updates the footer count accordingly.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Contracts, Scaffold, and Eval Spine | 3/3 | Complete | 2026-04-26 |
| 2. Deterministic Trust Services | 6/6 | Complete | 2026-04-26 |
| 3. CLI Setup, Onboarding, and TUI Controls | 4/4 | Complete | 2026-04-27 |
| 4. Graph Runtime and Agent Skills | 5/5 | Complete | 2026-04-27 |
| 5. Rules-First PF2e Vertical Slice | 5/5 | Complete | 2026-04-28 |
| 6. AI GM Story Loop | 4/8 | In progress | - |
| 7. Memory, Vault, and Resume Differentiator | 0/TBD | Not started | - |
| 8. Retcon, Repair, and Release Hardening | 0/TBD | Not started | - |
