# SagaSmith

## What This Is

SagaSmith is a local-first, single-player, AI-run tabletop RPG delivered as a Python CLI/TUI application. It aims to recreate the human-GM promise of "go anywhere, do anything" by coordinating specialized AI agents for onboarding, GM planning, rules adjudication, narration, and campaign memory, while deterministic services handle rules, dice, persistence, cost accounting, and safety.

The MVP targets solo Pathfinder 2e play in a terminal interface with persistent multi-session campaigns, player-provided LLM credentials, auditable mechanics, spoiler-safe campaign memory, and safety controls that remain active during play.

## Core Value

A solo player can start, play, quit, and resume an AI-run PF2e campaign where the story adapts to their choices while rules, memory, safety, cost, and persistence remain trustworthy.

## Requirements

### Validated

- [x] Phase 1 validated a local `uv` Python package scaffold, importable `sagasmith` package, Typer CLI entry point, and documented lint/format/type/test/smoke commands.
- [x] Phase 1 validated Pydantic v2 state contracts, persisted-state validation, JSON Schema export for 16 boundary/persisted models, and compact `SagaState` references.
- [x] Phase 1 validated a no-paid-call smoke spine with committed fixtures, schema round-trip checks, invalid-state rejection, compact-state invariants, and redaction canary coverage.

### Active

- [ ] Player can install the local CLI/TUI app and run the first-time setup without a hosted server.
- [ ] Player can provide OpenRouter credentials first, with direct-provider support behind the same model-agnostic interface.
- [ ] Player can complete onboarding that captures story preferences, content policy, house rules, budget, dice UX, campaign length, and character creation mode.
- [ ] Runtime persists `PlayerProfile`, `ContentPolicy`, `HouseRules`, and graph state through typed Pydantic models and JSON Schema validation.
- [ ] The game can run a first playable vertical slice with one level-1 pregenerated martial PC, one skill challenge, and one simple theater-of-mind combat encounter.
- [ ] Rules resolution is deterministic and auditable for degree of success, seeded d20 rolls, skill checks, strikes, initiative, action economy, HP changes, and roll logs.
- [ ] Oracle produces structured scene plans, hooks, inline NPCs, safety-aware reroutes, and mechanical encounter requests without narrating directly to the player.
- [ ] Orator is the only player-facing narrative voice, streams narration, respects dice UX, and never contradicts resolved mechanics.
- [ ] Archivist assembles bounded memory packets, resolves entities, writes canon, detects conflicts, and maintains spoiler-safe master/player vaults.
- [ ] The campaign memory layer stores canonical knowledge in Obsidian-compatible markdown vaults with SQLite, FTS5, LanceDB, and NetworkX as supporting or derived layers.
- [ ] Turn-close persistence checkpoints completed turns, prevents partial canonical vault writes, and supports quit/resume and rebuild/repair commands.
- [ ] Safety controls capture hard limits, soft limits, `/pause`, `/line`, redline rerouting, and player-visible safety event logging.
- [ ] CostGovernor tracks token/cost usage, warns at 70% and 90%, and hard-stops before budget is exceeded.
- [ ] Textual TUI exposes streaming narration, status panel, input prompt, dice overlay, safety bar, and required slash commands.
- [ ] LangGraph orchestration coordinates agent nodes, typed state, streaming, interrupts, checkpoints, and routing by gameplay phase or pillar.
- [ ] Agent Skills capability packages support progressive disclosure for agent/domain knowledge without stuffing every turn's prompt.
- [ ] Eval and regression coverage verifies rules examples, replay, memory recall, safety redlines, vault projection, cost enforcement, and MVP smoke flow.

### Out of Scope

- Multiplayer or party-based play - MVP is solo player, solo PC.
- Tactical grid/map-based combat - MVP uses theater-of-mind position tags only.
- GUI, web, mobile, or Tauri frontends - MVP is Textual TUI only.
- Image generation and rich visual art pipeline - Artist/ImageProvider remains placeholder-only.
- Standalone Cartographer, Puppeteer, or Villain agents - Oracle owns these concerns inline or defers them.
- PF2e levels above 3 - MVP rule scope is levels 1-3, with the first vertical slice limited to level 1.
- Spellcasting in the first vertical slice - deferred until the rules engine foundation is stable.
- Multiple rules systems or custom rule-system builder - PF2e is the only implemented system for MVP.
- Hosted server, cloud sync, or MMO/shared-world infrastructure - product remains local-first.
- Full graph database as source of truth - vault remains source of truth; graph databases are deferred derived-layer options only.
- Voice input/output - text-only terminal interaction for MVP.
- Community content/modding platform - post-MVP aspiration.

## Context

The repository contains the Phase 1 application scaffold: a `uv`-managed Python package named `ai-sagasmith`, import package `sagasmith`, Typer CLI entry point, strict quality tooling, Pydantic state contracts, JSON Schema export, and no-paid-call smoke/eval spine. Existing planning decisions name the GitHub repository `sagasmith`, PyPI/project package `ai-sagasmith`, and Python import package `sagasmith`.

The primary product specification lives in `docs/sagasmith/GAME_SPEC.md`. Supporting implementation contracts live in `docs/sagasmith/STATE_SCHEMA.md`, `docs/sagasmith/PF2E_MVP_SUBSET.md`, `docs/sagasmith/PERSISTENCE_SPEC.md`, `docs/sagasmith/LLM_PROVIDER_SPEC.md`, and `docs/sagasmith/VAULT_SCHEMA.md`. Agent capability catalogs live under `docs/sagasmith/agents/`. Deferred ideas and post-MVP expansion paths live in `docs/WISHLIST.md`.

The first implementation should prioritize a working vertical slice over full-system completeness: a local app that can configure an LLM provider, persist initial player/campaign records, validate schemas, run deterministic rules, produce streamed narrative, checkpoint turns, and prove memory/safety/cost boundaries on a small campaign fixture.

The game architecture is intentionally split between deterministic services and AI agents. AI agents propose, plan, summarize, and narrate; deterministic code owns rules math, roll RNG, schema validation, persistence ordering, cost accounting, command dispatch, and file-write atomicity.

Memory is a differentiator. SagaSmith must remember campaign facts across sessions using a two-vault model: a master vault with GM-only canon in app data, and a player vault projection that is safe to open in Obsidian without spoilers.

## Constraints

- **Runtime**: Python CLI/TUI application - local-first install, no server dependency.
- **UI**: Textual TUI for MVP - no GUI or web frontend in the first release.
- **Package management**: `uv` is available and preferred for project scaffolding.
- **Quality tools**: `ruff`, `pyright`, `pre-commit`, `textual-dev`, and `gitleaks` are installed globally for development workflow.
- **Orchestration**: LangGraph is accepted by ADR-0001 - implementation should not re-open framework selection unless a hard blocker appears.
- **Agent capability format**: Agent Skills filesystem format is accepted by ADR-0001 - implement a small first-party adapter before considering external SDK adoption.
- **LLM provider**: OpenRouter is first provider - direct providers use the same `LLMClient` abstraction later.
- **Secrets**: API keys must never be persisted to campaign files, vaults, transcripts, checkpoints, or debug logs.
- **Rules system**: PF2e only for MVP - deterministic engine is source of truth; LLMs may not invent modifiers, DCs, damage, HP changes, or conditions.
- **First slice**: Level 1 pregenerated martial PC, one skill challenge, one simple combat, two enemies maximum, no spellcasting.
- **Persistence**: Completed turns require SQLite transaction, LangGraph checkpoint, atomic master-vault writes, derived-index updates, and player-vault sync in the specified order.
- **Memory source of truth**: Obsidian-compatible markdown vaults remain canonical; FTS5, LanceDB, and NetworkX are rebuildable derived/read layers.
- **Safety**: Content policy enforcement is required before and after generation, with `/pause` and `/line` available during play.
- **Budget**: CostGovernor must warn once at 70% and 90%, and hard-stop before the next paid call would exceed budget.
- **Distribution**: Avoid JVM/server-heavy dependencies that undermine `pip install` local-first use.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use SagaSmith as product name, `ai-sagasmith` as package name, and `sagasmith` as import package | Keeps branding distinct while satisfying package/import conventions | - Pending |
| Build local-first Python CLI/TUI with Textual | Terminal application validates core RPG loop before investing in GUI complexity | - Pending |
| Use LangGraph for orchestration | Best fit for checkpointing, streaming, interrupts, model-agnostic stateful workflows, and auditable replay | - Pending |
| Use Agent Skills as per-agent capability format | Preserves context budget and keeps domain capabilities portable across frameworks | - Pending |
| Implement first-party LangGraph Skills adapter initially | Adapter is small and SagaSmith-specific needs are not yet proven enough for an external dependency | - Pending |
| Prefer OpenRouter as first LLM provider | BYOK model and broad model routing fit the product goal while keeping direct providers possible later | - Pending |
| Keep PF2e mechanics deterministic and local | Rules must be auditable, replayable, and not hallucinated by agents | - Pending |
| Limit first slice to one level-1 pregenerated martial PC | Reduces rules data and character creation complexity while proving gameplay loop | - Pending |
| Use two-vault memory architecture | Gives the player Obsidian-compatible campaign artifacts without exposing GM-only spoilers | - Pending |
| Keep vault as source of truth with rebuildable derived layers | Preserves local-first, file-system-first, git-friendly memory while allowing search and graph retrieval | - Pending |
| Defer standalone Artist, Cartographer, Puppeteer, and Villain agents | MVP validates narrative/memory/rules loop before adding specialized agent complexity | - Pending |
| Defer tactical maps, GUI, multiplayer, voice I/O, and custom rule systems | These are high-complexity expansions that do not block MVP core value | - Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-26 after Phase 1 completion*
