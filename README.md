# SagaSmith

**Local-first, single-player, AI-run tabletop RPG — in your terminal.**

SagaSmith is a Python CLI/TUI app that recreates the human-GM promise of *go anywhere, do anything* by coordinating specialized AI agents for planning, narration, and memory while deterministic services handle rules, dice, persistence, cost, and safety. The MVP targets solo Pathfinder 2e play with persistent multi-session campaigns, player-provided LLM credentials, auditable mechanics, spoiler-safe campaign memory, and always-on safety controls.

> **Core value.** A solo player can start, play, quit, and resume an AI-run PF2e campaign where the story adapts to their choices while rules, memory, safety, cost, and persistence remain trustworthy.

---

## Status

**Phase 7 of 8 — Memory, Vault, and Resume.** Roughly 93% of planned MVP work is complete. Not playable end-to-end yet; the AI GM story loop runs and deterministic mechanics work, but persistent memory, vault projection, and release hardening are still landing.

| Phase | Theme | State |
|------:|-------|-------|
| 1 | Contracts, scaffold, eval spine | Complete |
| 2 | Deterministic trust services (rules, dice, cost, persistence) | Complete |
| 3 | CLI setup, onboarding, TUI controls | Complete |
| 4 | LangGraph runtime + Agent Skills adapter | Complete |
| 5 | Rules-first PF2e vertical slice | Complete |
| 6 | AI GM story loop (Oracle / RulesLawyer / Orator / safety) | Complete |
| 7 | Memory, vault, and resume | In progress |
| 8 | Retcon, repair, and release hardening | Pending |

Live state lives in [.planning/STATE.md](.planning/STATE.md); the full roadmap is in [.planning/ROADMAP.md](.planning/ROADMAP.md).

---

## How it works

SagaSmith intentionally splits responsibility between deterministic services and AI agents. **AI agents propose, plan, summarize, and narrate. Deterministic code owns the math, the dice RNG, schema validation, persistence ordering, cost accounting, command dispatch, and file-write atomicity.** LLMs never invent modifiers, DCs, damage, HP changes, or conditions.

### Agents

| Agent | Role |
|-------|------|
| **Oracle** | World/seed generation and scene planning. Emits structured scene briefs and beats; never narrates to the player. |
| **RulesLawyer** | Translates player intent into deterministic mechanical proposals. Defers all math to the rules engine. |
| **Orator** | The only player-facing narrative voice. Streams beats, respects dice-UX preferences, and cannot contradict resolved mechanics. |
| **Archivist** | Resolves entities, assembles bounded MemoryPackets, writes canon, and projects a spoiler-safe player vault. |

Each agent's capabilities are packaged as **Agent Skills** — filesystem-format `SKILL.md` modules loaded on demand via a first-party adapter, so context stays compact and capabilities stay portable.

### Two-vault memory

Memory is the differentiator. Campaign canon lives in **Obsidian-compatible markdown vaults** that survive across sessions:

- **Master vault** — GM-only canon with full frontmatter, kept in app data.
- **Player vault projection** — safe to open in Obsidian during play; GM-only fields and foreshadowed content are stripped.

The vault is the source of truth. SQLite, FTS5, LanceDB, and NetworkX are rebuildable derived layers used for retrieval — never the canonical store.

### Trust boundaries

- **Rules.** Seeded d20 rolls and PF2e degree-of-success math are reproducible from ordered inputs. Every roll is logged and replayable.
- **Persistence.** Turn-close runs an ordered transaction: SQLite write → LangGraph checkpoint → atomic master-vault write → derived-index update → player-vault sync. No partial canonical writes.
- **Safety.** Pre- and post-generation gates plus `/pause` and `/line` commands; events are logged for the player.
- **Cost.** `CostGovernor` enforces a session budget with exactly-once 70% / 90% warnings and a hard pre-call stop.
- **Secrets.** API keys are read via keyring or env-reference and never written to campaigns, vaults, transcripts, checkpoints, or logs. A redaction canary runs on every persisted record.

---

## Requirements

- Python `>=3.12,<3.14`
- [`uv`](https://docs.astral.sh/uv/)
- `make` (optional)

## Install

```bash
uv sync --all-groups
uv run pre-commit install   # optional, one-time per clone
```

## Quickstart

```bash
uv run sagasmith --help        # discover commands
uv run sagasmith version
uv run sagasmith init          # create a local campaign
uv run sagasmith configure     # set LLM provider + budget
uv run sagasmith play          # launch the Textual TUI
uv run sagasmith demo          # provider-free demo path
```

In-TUI commands include `/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/clock`, `/budget`, `/pause`, `/line`, `/retcon`, `/settings`, and `/help`. Stubbed commands name the phase that will replace them.

> **BYO LLM.** OpenRouter is the first supported provider; direct providers reuse the same `LLMClient` interface. You supply the key — SagaSmith never ships one.

---

## Developer commands

| Task | Make target | Direct command |
|------|-------------|----------------|
| Install deps | `make install` | `uv sync --all-groups` |
| Lint | `make lint` | `uv run ruff check src tests` |
| Format | `make format` | `uv run ruff format src tests` |
| Format check | `make format-check` | `uv run ruff format --check src tests` |
| Type check | `make typecheck` | `uv run pyright` |
| Unit tests | `make test` | `uv run pytest -q` |
| No-paid-call smoke | `make smoke` | `uv run pytest -q -m smoke` |
| All pre-commit hooks | `make precommit` | `uv run pre-commit run --all-files` |

The smoke suite never makes paid LLM calls — it exercises schemas, rules, persistence ordering, redaction, and the vertical-slice mechanics against committed fixtures.

---

## Project layout

```text
src/sagasmith/
├── app/             Bootstrap, config, session identity, dependency wiring
├── cli/             Typer command entry points (init, play, configure, demo, smoke, schema)
├── tui/             Textual widgets, screens, events, display-only state
├── graph/           LangGraph orchestration, routing, streaming, thin nodes
├── agents/          Oracle, RulesLawyer, Orator, Archivist — prompts and adapters (no disk writes)
├── prompts/         Versioned prompt modules (system + user builders + JSON schemas)
├── rules/           Deterministic PF2e engine (degree-of-success, dice, combat, character)
├── services/        Dice, command dispatch, safety, cost, validation, redaction
├── providers/       Provider-neutral LLMClient + OpenRouter adapter
├── persistence/     SQLite migrations, repositories, turn-close ordering, checkpoint wiring
├── memory/          Vault IO, FTS5, NetworkX graph, hybrid memory packet assembly
├── vault/           Master/player vault writers, projection, resolver
├── onboarding/      9-phase onboarding state machine + persistence
├── schemas/         Pydantic v2 domain/runtime/provider/agent models + JSON Schema export
├── evals/           Replay, fixtures, safety/memory/cost/smoke harnesses
├── skills/          First-party Agent Skills (SKILL.md catalog)
└── skills_adapter/  YAML-lite loader, store, catalog, errors
```

---

## Documentation

Specifications and planning artifacts live alongside the code:

- [docs/specs/GAME_SPEC.md](docs/specs/GAME_SPEC.md) — primary product specification
- [docs/specs/STATE_SCHEMA.md](docs/specs/STATE_SCHEMA.md) — typed state contracts
- [docs/specs/PF2E_MVP_SUBSET.md](docs/specs/PF2E_MVP_SUBSET.md) — first-slice PF2e scope
- [docs/specs/PERSISTENCE_SPEC.md](docs/specs/PERSISTENCE_SPEC.md) — turn-close ordering and SQLite schema
- [docs/specs/LLM_PROVIDER_SPEC.md](docs/specs/LLM_PROVIDER_SPEC.md) — `LLMClient` contract, retries, redaction
- [docs/specs/VAULT_SCHEMA.md](docs/specs/VAULT_SCHEMA.md) — two-vault model
- [docs/specs/ADR-0001-orchestration-and-skills.md](docs/specs/ADR-0001-orchestration-and-skills.md) — LangGraph + Agent Skills decision
- [docs/specs/agents/](docs/specs/agents/) — per-agent capability catalogs
- [.planning/PROJECT.md](.planning/PROJECT.md) — living project context, constraints, decisions
- [.planning/ROADMAP.md](.planning/ROADMAP.md) — phase structure and success criteria
- [.planning/REQUIREMENTS.md](.planning/REQUIREMENTS.md) — v1 requirements with traceability
- [.planning/STATE.md](.planning/STATE.md) — current phase, progress, continuity notes
- [docs/WISHLIST.md](docs/WISHLIST.md) — deferred ideas and post-MVP expansion

---

## Scope guardrails

**MVP is deliberately narrow.** Out of scope for v1: multiplayer, tactical maps, GUI/web/mobile frontends, image generation, hosted server, voice I/O, custom rule systems, levels above 3, and spellcasting in the first vertical slice. See [.planning/PROJECT.md](.planning/PROJECT.md) for the full list and the rationale behind each deferral.

## Secrets

API keys are never committed and never written to campaign files, vaults, transcripts, checkpoints, or logs. Provider credentials resolve through keyring or environment-variable references at call time.

## License

SagaSmith is dual-licensed:

- **Source code, schemas, tooling, tests, and original documentation** are licensed under the **Apache License, Version 2.0**. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
- **Pathfinder 2e Remaster rules content** bundled with the project (mechanics, stat blocks, conditions, degree-of-success math, monster and equipment data) is licensed under the **ORC License v1.0** administered by Azora Law. See [LICENSE-ORC.md](LICENSE-ORC.md) for the Licensed Material and Reserved Material notices.

The two licenses cover disjoint material — Apache 2.0 does not relicense ORC content, and ORC does not relicense Apache code. Downstream users must comply with both for the portions each one covers.

SagaSmith is an independent product and is not published, endorsed, or specifically approved by Paizo Inc. Pathfinder is a registered trademark of Paizo Inc.
