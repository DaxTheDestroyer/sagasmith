# Project Research Summary

**Project:** SagaSmith  
**Domain:** Local-first AI-run solo tabletop RPG assistant / AI GM in a Textual TUI  
**Researched:** 2026-04-26  
**Confidence:** HIGH overall for product direction, stack shape, architecture, and critical gates; MEDIUM for fast-moving provider/version details and a few integration seams.

## Executive Summary

SagaSmith should be built as a local-first Python TUI product that lets a solo player bring their own LLM key, complete a short setup, play a PF2e-inspired adventure loop, quit, resume, and inspect durable local campaign artifacts. The expert pattern is not “one big AI GM prompt.” It is a typed orchestration runtime where LLM agents plan, summarize, and narrate while deterministic services own rules, dice, persistence, safety, cost, secrets, and vault writes.

The recommended MVP is a narrow but trustworthy vertical slice: Textual UI, Typer CLI, LangGraph turn orchestration, Pydantic schemas, SQLite checkpoints/state, OpenRouter through a first-party HTTPX `LLMClient`, a deterministic PF2e level-1 martial subset, and Obsidian-compatible master/player vaults. LanceDB and NetworkX are appropriate derived read layers, but should not become authoritative storage.

The main risk is building an entertaining AI story demo that quietly corrupts rules, canon, safety, budget, or replay. Mitigate this by front-loading contracts, deterministic services, crash-safe turn lifecycle, redacted provider/cost handling, invariant evals, and two-vault spoiler gates before adding feature breadth, richer agents, spellcasting, tactical maps, or multiplayer.

## Key Findings

### Recommended Stack

SagaSmith should be a Python 3.12+ package managed by `uv`, with a single in-process CLI/TUI runtime. Avoid a hosted API server, FastAPI backend, web UI, cloud sync, heavyweight graph database, vendor-specific agent SDK, or local LLM/runtime dependency in the MVP.

**Core technologies:**
- **Python `>=3.12,<3.14` + uv** — stable local-first packaging, reproducible `uv.lock`, and Windows/macOS/Linux friendliness.
- **Textual `>=8,<9` + Typer `>=0.25,<1`** — Textual is the MVP play surface; Typer owns lifecycle/admin commands such as `init`, `play`, `vault rebuild`, `vault sync`, `config`, and `demo`.
- **LangGraph `>=1.1,<2` + `langgraph-checkpoint-sqlite >=3,<4`** — durable state graph, streaming, interrupts, checkpoint/resume, and replay/time-travel semantics match turn lifecycle needs.
- **Pydantic 2.x + pydantic-settings** — canonical schema boundary for persisted objects, agent structured outputs, JSON Schema export, and strict validation.
- **SQLite + explicit migrations/repositories** — transactional local source for campaign metadata, turns, transcripts, roll logs, cost logs, state deltas, and checkpoints.
- **Obsidian-compatible markdown vaults** — master vault is canonical campaign memory; player vault is spoiler-safe projection.
- **HTTPX first-party OpenRouter client** — auditable streaming, retries, redacted logging, structured output handling, and usage/cost capture behind a provider-neutral `LLMClient` protocol.
- **keyring + env var references** — API keys must never be persisted in SQLite, vaults, checkpoints, transcripts, logs, or diagnostics.
- **LanceDB + NetworkX + SQLite FTS5** — derived, rebuildable memory retrieval layers; never sources of truth.
- **pytest, pytest-asyncio, respx, hypothesis, ruff, pyright, pre-commit, gitleaks** — required quality gate for deterministic replay, HTTP contracts, Textual async behavior, schema round trips, PF2e math, typing, linting, and secret scanning.

**Important stack open points:** prototype LangGraph SQLite transaction sharing; validate OpenRouter structured-output/streaming behavior for default models; choose markdown/frontmatter parser after Obsidian fixture tests; decide embedding packaging during Archivist work.

### Table Stakes and Differentiators

SagaSmith competes best by being trustworthy and local-first, not by matching cloud AI RPG platforms on visuals, multiplayer, maps, publishing, or content breadth. V1 succeeds if the user can install locally, configure BYOK OpenRouter, onboard, play a meaningful scene with deterministic mechanics, quit/resume, and see persistent memory work.

**Must have (table stakes):**
- Local install/first-run setup that creates campaign directory, SQLite DB, and player vault.
- BYOK provider setup with keyring/env references, redacted logs, and OpenRouter first.
- Guided onboarding under ~15 minutes for profile, content policy, house rules, budget, dice UX, and campaign premise.
- Free-form natural-language input for scene actions.
- Streaming narration with one authoritative player-facing Orator voice.
- Deterministic dice, roll logs, seeded replay, and auditable PF2e first-slice resolution.
- Pregen level-1 martial PC, `/sheet`, minimal `/inventory`, status panel, in-game clock, and dice opacity modes.
- Save/quit/resume after each completed turn and recovery from stream/network/vault failures.
- Transcript/scrollback, `/recap`, persistent memory, entity resolution, and minimal retcon.
- Two-vault spoiler-safe memory and Obsidian-compatible player artifacts.
- Runtime safety controls: `/pause`, `/line`, hard/soft limits, fade/reroute, visible safety event log.
- Cost visibility: `/budget`, 70%/90% warnings, and hard stop before the next paid call.
- Eval/smoke regression for install/init/onboard/play skill/combat/quit/resume, memory recall, safety redlines, and budget enforcement.

**Should have (differentiators protected in roadmap):**
- Local-first durable campaign artifact that the player owns.
- Two-vault spoiler-safe memory with GM-only master state and player-safe Obsidian projection.
- Deterministic-service / AI-agent split that makes improvisation auditable.
- Auditable PF2e math under improvised narrative.
- Safety as an in-fiction reroute system, not just a final prose filter.
- First-class CostGovernor for BYOK trust.
- Canon conflict surfacing and callback ledger / seed-to-payoff tracking.
- Rebuildable derived memory layers and repair commands.
- Typed structured outputs for agents.
- Minimal TUI with always-visible trust surfaces: state, dice, safety, and budget.

**Defer to V2/post-MVP:**
- Guided/player-led character creation beyond a pregen first slice.
- Spellcasting, full PF2e levels 1-3 breadth, levels 4+, multiple rules systems, and homebrew rules DSL.
- Tactical grid, battlemaps, CartographerAgent, rich dungeon/hex generation.
- GUI/web/mobile frontends, multiplayer, party companions, voice, community sharing, publishing, scripting, and cloud sync.
- Real ArtistAgent/image generation, standalone PuppeteerAgent/VillainAgent, Director mode, and public marketplace features.
- Dedicated graph database unless NetworkX/derived indices fail at long-campaign scale.

### Architecture Shape

Use a local-first event-driven Textual shell around a LangGraph turn engine. The central rule is: **LLM agents propose, interpret, plan, summarize, and narrate; deterministic services validate, resolve, persist, account, and write files.** Keep graph nodes thin; they orchestrate calls to agents, services, persistence, and memory rather than owning UI, SQL, vault parsing, PF2e math, or provider-specific details.

**Recommended package shape:**
1. `sagasmith.app` / `sagasmith.cli` — bootstrap, config, session identity, dependency wiring, command entrypoints.
2. `sagasmith.tui` — Textual widgets/screens/events; display-only state and command input.
3. `sagasmith.graph` — typed `StateGraph[SagaState]`, routing, streaming/update normalization, interrupts, thin nodes.
4. `sagasmith.agents` — prompts and adapters for Onboarding, Oracle, Rules Lawyer, Archivist, Orator; no direct disk writes.
5. `sagasmith.services` — deterministic dice, PF2e rules, command dispatch, safety, cost, validation, atomic files.
6. `sagasmith.providers` — `LLMClient` protocol, OpenRouter HTTPX implementation, pricing/usage normalization.
7. `sagasmith.persistence` — SQLite migrations/repositories, turn-close transaction orchestration, LangGraph checkpointer wiring.
8. `sagasmith.memory` — vault IO, player projection, FTS5, LanceDB, NetworkX, retrieval, rebuild/sync.
9. `sagasmith.schemas` — Pydantic domain/runtime/provider/agent models and JSON Schema export.
10. `sagasmith.evals` — deterministic replay, fixture campaigns, safety, memory, cost, and smoke harnesses.

**Turn graph shape:** player input/command gate → safety pre-gate → Archivist read/MemoryPacket → Oracle structured scene plan → intent/rules gate → deterministic RulesLawyer/PF2e/DiceService if needed → Orator streaming → safety post-gate → Archivist write/persist → prompt return.

**Critical boundary rules:** no provider imports outside `providers`; no Textual imports outside `tui`/bootstrap; no vault writes outside memory/persistence orchestration; no random dice outside `DiceService`; no plaintext API keys anywhere persistent; no LLM-authored mechanics deltas without deterministic validation; no Orator scene planning.

### Critical Pitfalls and Gates

1. **LLM agents become source of truth** — prevent with typed Pydantic outputs, allowed `StateDelta` policies, deterministic rules/cost/safety/persistence services, and eval traces.
2. **Long context mistaken for memory** — prevent with master vault as source of truth, bounded `MemoryPacket`, visibility-aware retrieval, entity resolution, and recall/spoiler fixtures.
3. **Generic save system instead of crash-safe turn lifecycle** — enforce SQLite transaction + checkpoint first, atomic vault writes after commit, derived sync after vault write, repair flags, and crash-injection tests.
4. **PF2e scope swallows MVP** — hard-cap first slice to level-1 martial PC, skill check, initiative, Strike, HP damage, two enemies max, theater-of-mind, no spellcasting.
5. **Transcript quality hides broken reliability** — phase-block with invariant tests for schemas, replay, state deltas, vault projection, safety, cost, and memory instead of exact-prose assertions.
6. **Cost/provider trust added too late** — build `LLMClient`, CostGovernor, preflight estimates, retry budget checks, pricing metadata, and redacted logs before real agents.
7. **TUI freezes during thinking/streaming** — run graph/provider work in Textual workers, marshal UI updates safely, keep `/pause` and `/line` available during streaming.
8. **Safety only filters final prose** — pre-gate scene intent, post-gate prose, make `/line` reroute Oracle plans, persist visible safety events.
9. **Prompt injection/canon poisoning through input or vault files** — treat all player text, transcripts, and retrieved markdown as untrusted data; delimit retrieval; never ingest player vault edits as canon.
10. **Scope creep through deferred agents/features** — keep wishlist agents as Oracle skills/placeholders until MVP gates are green.

**Non-negotiable gates for roadmap acceptance:** LLM boundary gate, deterministic rules gate, persistence/replay gate, memory/canon gate, safety gate, cost/provider gate, TUI responsiveness gate, eval/release gate, and scope gate.

## Implications for Roadmap

Research strongly supports a trust-before-breadth roadmap. Build deterministic contracts and storage before impressive narration; build provider/cost/safety controls before paid agent loops; prove one narrow PF2e adventure before memory depth and rules expansion.

### Phase 0: Contracts, Scaffold, and Eval Spine

**Rationale:** Every later component depends on stable schemas, package layout, state-delta authority, and invariant tests. Prompt work before this risks unreviewable agent authority leaks.

**Delivers:** `uv` package scaffold, CLI skeleton, Pydantic schemas/JSON Schema export, `SagaState` reducer rules, state-delta authorization policy, eval harness skeleton, redaction canary fixtures, first-party SkillStore skeleton.

**Addresses:** local install groundwork, typed structured outputs, deterministic-service / agent split.

**Avoids:** LLM source-of-truth leaks, eval theater, skill bloat, privacy leaks.

**Gate:** models round-trip; invalid agent outputs are rejected; unauthorized deltas fail closed; eval harness runs in CI; redaction canary test passes.

### Phase 1: Deterministic Core, Provider, Safety, and Persistence Spine

**Rationale:** Rules, cost, secrets, checkpoints, and turn-close ordering are trust foundations. They must exist before a real Orator streams canonical prose.

**Delivers:** DiceService, PF2e first-slice math, roll logs, SQLite schema/migrations, repositories, LangGraph SQLite checkpointer prototype, turn lifecycle, CostGovernor, SafetyGuard models/commands, `LLMClient` protocol, OpenRouter mock contract tests, keyring/env secret references.

**Addresses:** deterministic dice, auditable PF2e core, save/resume foundation, budget setup, safety setup, BYOK provider setup.

**Avoids:** PF2e hallucination, replay illusion, unbounded consumption, plaintext secret leakage, brittle save system.

**Gate:** degree-of-success/natural 1/20/skill/Strike/initiative/HP tests pass; seeded replay reproduces logs; crash-injection persistence tests pass; no plaintext secrets persist; budget hard-stop occurs before paid call.

### Phase 2: TUI Control Surface and Onboarding

**Rationale:** The player contract must be established before gameplay: profile, safety, budget, dice UX, settings, and responsive controls. The TUI must prove it can stay responsive under graph/provider latency.

**Delivers:** Textual layout (transcript/status/input/safety bar), command registry, `/help`, `/sheet`, `/clock`, `/budget`, `/settings`, `/pause`, `/line`, onboarding interview/review, provider validation before long onboarding, p50 first-token instrumentation hooks.

**Addresses:** guided onboarding, required slash commands, trust UI, safety controls, cost visibility, character sheet visibility.

**Avoids:** onboarding friction, frozen terminal, safety commands only working between turns.

**Gate:** setup reaches first playable prompt quickly; slash commands remain responsive during worker activity; `/pause` and `/line` are graph states/interrupts; budget/safety state visible.

### Phase 3: Rules-First Playable Vertical Slice

**Rationale:** Prove one skill challenge and one simple combat with deterministic mechanics before allowing richer AI improvisation or memory complexity.

**Delivers:** level-1 martial pregen, skill check vs fixed DC, Perception initiative, Strike vs AC, HP damage, simple action economy, theater-of-mind positions, dice overlay/reveal mode, replay fixtures.

**Addresses:** skill challenge + simple combat vertical slice, dice UX, status panel, roll replay tests, minimal inventory/clock integration.

**Avoids:** PF2e scope creep, temporary LLM adjudication, tactical-grid drift, spellcasting complexity.

**Gate:** first-slice mechanical regression suite green; unsupported mechanics fail closed with player-facing message; Orator/Oracle cannot mutate mechanical state.

### Phase 4: AI GM Story Loop

**Rationale:** With deterministic services and TUI controls in place, add the actual playable AI loop while preserving authority boundaries.

**Delivers:** OnboardingAgent structured outputs if not already complete, Oracle `SceneBrief` planning, RulesLawyer wrapper over deterministic services, Orator streaming narration, safety pre/post gates, provider retry/repair behavior, transcript persistence, one curated sample hook with limited choice.

**Addresses:** campaign start/hook selection, free-form natural-language input, streaming narration, one authoritative narrative voice, crash/network failure recovery, campaign transcript.

**Avoids:** Orator mechanics contradictions, provider lock-in, prompt injection, safety-only-final-filter failure, cost surprises.

**Gate:** init → configure fake/real provider → onboard → play skill challenge → simple combat → quit/resume passes; Orator never contradicts `CheckResult`; provider timeout recovers without corrupting canon; safety redline and budget hard-stop evals pass.

### Phase 5: Memory, Vault, and Resume Differentiator

**Rationale:** Once the game loop works, implement the differentiator that makes SagaSmith more than a chatbot: durable local memory and spoiler-safe Obsidian artifacts.

**Delivers:** master vault page schema/writes, player vault projection, GM-only stripping, `index.md`/`log.md`, slug+alias entity resolution, bounded `MemoryPacket`, FTS5 read path, basic `vault rebuild`/`vault sync`, `/recap`, resume recall, initial callback ledger.

**Addresses:** persistent campaign memory, spoiler-safe notes, Obsidian player vault, entity resolution, recap, rebuildable derived layers, callback tracking.

**Avoids:** long-context memory trap, duplicate NPCs, spoiler leaks, player vault as canon, derived index as source of truth.

**Gate:** zero GM-only leakage in player vault fixtures; session-1 NPC recalled in later-session fixture; player vault edits ignored as canon; memory packet respects token cap/visibility; rebuild/sync works from master vault.

### Phase 6: Retcon, Repair, and MVP Hardening

**Rationale:** Multi-session trust requires recovery paths, migrations, retcon behavior, release smoke suites, and regression dashboards before broader content or rules expansion.

**Delivers:** robust `/retcon` for last completed turn, inverse/replayable state deltas, vault/index repair UX, stale-index detection, checkpoint/schema migrations, network-disabled replay, release eval suite, sanitized diagnostics export.

**Addresses:** retcon last turn, crash/network recovery, save/resume durability, eval/smoke regression, local-first privacy.

**Avoids:** partial canon writes, checkpoint migration failure, retcon inconsistency, hidden privacy leaks.

**Gate:** `/retcon` repairs DB/vault/index for simple cases or blocks safely; network-disabled replay passes; install→init→onboard→play→quit/resume→recap green; release safety/cost/latency/memory suites pass.

### Phase 7: Full MVP Expansion and Post-MVP Candidates

**Rationale:** Only after core loop reliability should the roadmap expand rules breadth and player customization.

**Delivers:** guided character creation, selected levels 1-3 PF2e expansion, additional conditions/actions, richer NPC/callback behavior, optional LanceDB/NetworkX depth if FTS/vault retrieval is insufficient.

**Addresses:** full MVP beyond first slice and selected differentiator depth.

**Avoids:** premature spellcasting, levels 4+, tactical maps, multiplayer, GUI, image generation, public sharing, or standalone deferred agents.

**Gate:** any promoted wishlist item must include written rationale, state contract, eval plan, cost impact, rollback plan, and scope-change approval.

### Phase Ordering Rationale

- Contracts and deterministic services precede prompts because agent outputs must be validated before crossing boundaries.
- Persistence precedes long gameplay because save/resume, retcon, replay, and vault repair are architectural lifecycle concerns, not late UI features.
- Provider/cost/safety precede real agents because every paid/safety-sensitive LLM call must be gated before it occurs.
- TUI responsiveness is early because safety controls are meaningless if the terminal freezes during streaming.
- Memory/vault comes after the playable loop but before MVP hardening because it is SagaSmith’s primary product differentiator.
- Rules breadth, new agents, visuals, maps, multiplayer, and content platforms remain explicitly post-MVP until trust gates pass.

### Research Flags

Phases likely needing deeper research or spikes during planning:
- **Phase 1:** LangGraph SQLite checkpointer transaction integration with SagaSmith turn-close ordering.
- **Phase 1/4:** OpenRouter structured-output and streaming behavior across selected default models, including usage/cost reporting.
- **Phase 2/4:** Textual worker + LangGraph streaming integration under artificial latency and cancellation.
- **Phase 5:** Markdown/frontmatter round-tripping against Obsidian fixtures; spoiler-safe projection edge cases.
- **Phase 5/7:** Embedding strategy for LanceDB without heavy base-install ML dependencies.
- **Phase 6:** Retcon inverse-delta design and checkpoint/schema migration paths.

Phases with standard patterns where extra research can usually be skipped:
- **Phase 0:** Python package scaffold, Pydantic model validation, JSON Schema export, ruff/pyright/pytest setup.
- **Phase 1 deterministic rules:** PF2e first-slice math and seeded dice are spec/fixture-driven once scope is fixed.
- **Phase 2 basic CLI/TUI commands:** Typer/Textual command and widget patterns are well documented.
- **Phase 6 basic eval harness:** invariant-first pytest/respx/hypothesis patterns are standard; domain fixtures matter more than further library research.

## Open Questions

- **LangGraph checkpoint transaction sharing:** Can `SqliteSaver` participate safely in the same SQLite transaction as SagaSmith turn-close writes, or is a coordinated adapter required?
- **OpenRouter structured outputs:** Which default models reliably support JSON Schema outputs and streaming usage metadata? How should repair/fallback work by model class?
- **Markdown/frontmatter parser:** Is `python-frontmatter` sufficient for Obsidian-compatible round trips, or should vault writes lean on `ruamel.yaml` plus custom markdown handling?
- **Embedding model packaging:** Should embeddings be provider-generated, local optional extras, or deferred until LanceDB semantic retrieval is necessary?
- **Pre-call cost estimation:** What pricing table/update strategy is conservative enough to hard-stop before the next paid call?
- **Installer/distribution path:** Is `pipx install ai-sagasmith` reliable with Textual, keyring, and LanceDB on supported OSes?
- **Retcon depth:** What is the safe cutoff between automatic inverse-delta rollback and manual repair/blocked retcon?

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core shape is locked by project specs/ADR and verified against current docs. Exact version pins are MEDIUM because AI/provider libraries move quickly. |
| Features | HIGH | MVP table stakes and differentiators are strongly supported by in-repo specs and external AI RPG/solo RPG ecosystem signals. |
| Architecture | HIGH | Component boundaries, graph shape, state ownership, persistence ordering, and test architecture are grounded in SagaSmith specs; LangGraph/Textual integration details need spikes. |
| Pitfalls | HIGH | Critical pitfalls derive directly from local-first, LLM, persistence, safety, cost, and TTRPG rule constraints; external AI-agent observations are MEDIUM where less SagaSmith-specific. |

**Overall confidence:** HIGH for roadmap direction and MVP boundaries; MEDIUM for specific provider/checkpoint/parser/embedding implementation decisions that need phase spikes.

### Gaps to Address

- **Checkpoint/transaction integration:** Prototype in Phase 1 before finalizing persistence tasks.
- **Provider model matrix:** Establish default OpenRouter model set and schema/streaming/cost behavior before Phase 4 prompt work.
- **Vault formatting compatibility:** Create seed Obsidian fixtures and round-trip tests before committing to parser/writer details.
- **Long-session memory quality:** Use 10-session recall, duplicate-entity, and spoiler fixtures before expanding campaign length.
- **Cost metadata freshness:** Define pricing metadata ownership and stale-price behavior before exposing hard budget claims.
- **Release packaging:** Test Windows/macOS/Linux install/keyring/Textual/LanceDB behavior before public packaging promises.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — project constraints and local-first product direction.
- `docs/specs/GAME_SPEC.md` — runtime/product behavior, MVP acceptance, agents, safety, save/resume.
- `docs/specs/ADR-0001-orchestration-and-skills.md` — LangGraph and first-party Agent Skills decision.
- `docs/specs/STATE_SCHEMA.md` — Pydantic/JSON Schema and compact `SagaState` contracts.
- `docs/specs/PERSISTENCE_SPEC.md` — SQLite/checkpoint/vault ordering, repair, rebuild semantics.
- `docs/specs/LLM_PROVIDER_SPEC.md` — BYOK provider abstraction, OpenRouter-first, streaming, structured JSON, retries, secrets, cost.
- `docs/specs/VAULT_SCHEMA.md` — Obsidian two-vault model, visibility, derived indices.
- `docs/specs/PF2E_MVP_SUBSET.md` — deterministic PF2e first-slice scope.
- `docs/specs/agents/*.md` — agent roles, skills, and service capability boundaries.
- `docs/WISHLIST.md` — explicitly deferred/post-MVP capabilities.

### Documentation and official sources (HIGH to MEDIUM-HIGH confidence)
- Context7 LangGraph docs — checkpoints, streaming, interrupts, `Command(resume=...)`, state history/time travel.
- Context7 Textual docs — workers, async/thread background work, `call_from_thread`, test pilot patterns.
- Context7 Pydantic docs — strict validation, JSON validation, `TypeAdapter`, JSON Schema generation.
- Context7 uv docs — `uv init`, `uv add`, `uv lock`, `uv sync`, dependency groups, build/publish.
- Context7 LanceDB docs — embedded local connections, vector/FTS/hybrid search, reranking.
- Context7 HTTPX docs — streaming, timeouts, event hooks.
- Context7 Typer docs — typed CLI commands/subcommands and Rich integration.
- Context7 NetworkX docs — graph/path/topology algorithms.
- OpenRouter official docs — OpenAI-compatible chat completions, streaming/API support, Python examples, SDK note.
- OWASP Top 10 for LLM Applications 2025 — prompt injection, sensitive information disclosure, excessive agency, vector/embedding weaknesses, unbounded consumption.

### Secondary ecosystem sources (MEDIUM confidence)
- Friends & Fables official about page — AI GM/worldbuilding/stat/note tracking expectations.
- AI Dungeon official guidebook and safety docs — memory/story cards/scenarios/safety controls expectations.
- Mythic GME 2e app page — solo oracle app expectations: fate checks, scene tracking, journals, lists, dice, local storage/export/import.
- LitRPG Adventures official site — RPG content generator categories and market expectations.
- TechCrunch coverage of Latitude Voyage — AI RPG platform direction around custom worlds, NPC interaction, deterministic systems, persistence.
- One Page Solo Engine public app/listing results — solo oracle/save/journal/dice feature expectations.
- PyPI JSON metadata checked 2026-04-26 — package version references.

---
*Research completed: 2026-04-26*  
*Ready for roadmap: yes*
