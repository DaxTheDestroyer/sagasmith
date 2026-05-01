# Technology Stack

**Project:** SagaSmith  
**Research dimension:** Stack for local-first Python AI TTRPG CLI/TUI runtime  
**Researched:** 2026-04-26  
**Overall confidence:** HIGH for locked stack shape; MEDIUM for exact version pins because this is a fast-moving AI ecosystem.

## Executive Recommendation

Build SagaSmith as a **Python 3.12+ local-first package** managed by **uv**, with **Textual** as the only MVP UI, **Typer** as the command entrypoint, **LangGraph 1.x** as the orchestration runtime, **Pydantic 2.x** as the schema boundary, **SQLite** as the transactional local store and LangGraph checkpoint backend, and **Obsidian-compatible markdown vaults** as the canonical campaign memory source of truth. Use **LanceDB** and **NetworkX** only as rebuildable derived read layers, never as authoritative storage.

Do **not** introduce a hosted API server, FastAPI backend, web UI, cloud sync, heavyweight graph database, or vendor-specific agent SDK in the MVP. Those choices conflict with the accepted local-first/TUI/BYOK decisions in `.planning/PROJECT.md` and `docs/sagasmith/ADR-0001-orchestration-and-skills.md`.

The best implementation shape is a small number of explicit deterministic services wrapped by LangGraph nodes:

- `sagasmith.graph`: typed `StateGraph`, node routing, checkpoint/resume glue.
- `sagasmith.agents`: Onboarding, Oracle, Rules Lawyer, Archivist, Orator nodes.
- `sagasmith.services`: dice, PF2e rules, safety, cost, persistence, provider client, vault sync.
- `sagasmith.ui`: Textual app, widgets, slash-command dispatch, streaming transcript.
- `sagasmith.cli`: Typer commands (`init`, `play`, `vault rebuild`, `vault sync`, `config`, `demo`).
- `sagasmith.skills`: first-party Agent Skills adapter and skill package loading.

Use **OpenRouter as the first provider through a first-party `LLMClient` abstraction** implemented with **HTTPX** against OpenRouter's OpenAI-compatible REST API. The official OpenRouter Python SDK exists, but the MVP needs precise streaming, redacted logging, retry, cost, and schema handling; a thin HTTPX client is easier to audit and test. Add direct providers later behind the same protocol.

## Core Stack

| Layer | Recommendation | Version guidance | Confidence | Why |
|---|---:|---|---|---|
| Python runtime | Python | `>=3.12,<3.14` initially | HIGH | Python 3.12 is mature, widely supported by AI/data libraries, and avoids betting the initial package on newest-interpreter edge cases. Re-evaluate Python 3.13 once all pinned dependencies and PyInstaller/installer paths are clean. |
| Package/project tooling | uv | Current PyPI: `0.11.7`; require recent `uv` and commit `uv.lock` | HIGH | uv is now a standard fast Python project manager with lockfiles, dependency groups, build/publish support, and Windows support. It aligns with project constraints and replaces Poetry/pip-tools/virtualenv for this greenfield project. |
| Project metadata/build | `pyproject.toml` with hatchling or uv default build backend | Use uv-generated defaults | HIGH | Simple PEP 621 project metadata, no setup.py, reproducible lockfile, easy CLI script entrypoint for `ttrpg`/`sagasmith`. |
| Orchestration | LangGraph | Current PyPI: `langgraph==1.1.9`; depend on `langgraph>=1.1,<2` | HIGH | ADR-0001 accepts LangGraph. Current docs verify `StateGraph`, durable checkpointing, streaming modes, and `interrupt()` for human-in-the-loop flows. Best fit for turn checkpoints, `/pause`, `/line`, replay, and conditional routing. |
| Checkpoint backend | `langgraph-checkpoint-sqlite` | Current PyPI: `3.0.3`; depend on compatible `>=3,<4` | HIGH | Matches the persistence spec: local SQLite, per-thread checkpoints, no server. Use the same campaign DB file or a dedicated SQLite connection in the same app-data area, but coordinate writes explicitly with SagaSmith's transaction order. |
| TUI | Textual | Current PyPI: `8.2.4`; depend on `textual>=8,<9` | HIGH | Textual is the right MVP UI: Python-native, terminal-first, supports widgets/screens, command palette patterns, test pilot APIs, and streaming UI updates. It should own the live play surface. |
| CLI | Typer | Current PyPI: `0.25.0`; depend on `typer>=0.25,<1` | HIGH | Typer gives typed subcommands, Rich help, shell completion, and simple packaging. Use it for lifecycle/admin commands and to launch the Textual app. |
| Terminal rendering | Rich | Current PyPI: `15.0.0`; mostly transitive via Textual/Typer | HIGH | Textual/Typer integrate with Rich. Use directly only for non-TUI CLI output and diagnostics. |
| Data validation | Pydantic | Current PyPI: `2.13.3`; depend on `pydantic>=2.13,<3` | HIGH | Specs require Pydantic models and JSON Schema. Pydantic v2 supports strict validation, `TypeAdapter`, `model_json_schema()`, and fast model validation. This should be the canonical schema boundary. |
| Settings | `pydantic-settings` | Current PyPI: `2.14.0`; depend on `>=2.14,<3` | HIGH | Use for environment/development overrides and typed app config. Do not store player API keys here except as environment-variable references. |
| Local transactional DB | SQLite stdlib + SQLAlchemy Core or SQLModel selectively | SQLite from Python stdlib; SQLModel current PyPI `0.0.38` if ORM used | MEDIUM | SQLite is locked by specs. Prefer explicit SQL migrations and SQLAlchemy Core-style table operations for checkpoint/turn-order control. Use SQLModel only for simple tables if it reduces boilerplate; avoid making persistence models double as domain models. |
| Full-text search | SQLite FTS5 | Built into modern SQLite builds | HIGH | Required derived layer. It is local, fast, rebuildable, and sufficient for exact phrase/entity searches over vault markdown. |
| Vector retrieval | LanceDB | Current PyPI: `0.30.2`; depend on `lancedb>=0.30,<1` | HIGH | Official docs support embedded local connections, vector search, FTS, hybrid search, and reranking. Best fit for local-first semantic entity resolution without running a vector server. |
| Graph retrieval | NetworkX | Current PyPI: `3.6.1`; depend on `networkx>=3.6,<4` | HIGH | Correct scale and deployment shape for MVP vault topology queries. Rebuild from wikilinks/frontmatter on startup or repair. No server/database required. |
| LLM HTTP client | HTTPX | Current PyPI: `0.28.1`; depend on `httpx>=0.28,<1` | HIGH | HTTPX supports sync/async clients, streaming responses, timeouts, and event hooks for redacted logging. Better control than opaque provider SDK wrappers for SagaSmith's cost/safety/retry contracts. |
| First LLM provider | OpenRouter REST API | API endpoint `https://openrouter.ai/api/v1/chat/completions`; model IDs configured by user | HIGH | OpenRouter official docs verify OpenAI-compatible chat completions, optional attribution headers, streaming support, and structured-output support in the platform. It matches BYOK and broad model routing. |
| Direct-provider compatibility | First-party `LLMClient` Protocol | No dependency until provider is implemented | HIGH | Specs require provider-agnostic runtime. Keep provider calls below a stable protocol with `complete()` and `stream()` returning SagaSmith-owned response/event models. |
| Secrets | keyring + env var references | Current PyPI: `keyring==25.7.0`; depend on `keyring>=25,<26` | HIGH | `docs/sagasmith/LLM_PROVIDER_SPEC.md` requires OS keyring preferred and env var references for development. Never persist plaintext keys in SQLite campaign rows, vaults, checkpoints, or logs. |
| App directories | platformdirs | Current PyPI: `4.9.6`; depend on `platformdirs>=4,<5` | HIGH | Needed for predictable app-data paths across Windows/macOS/Linux (`%APPDATA%`, `~/Library/Application Support`, XDG). This matters for master vault, DBs, LanceDB, logs. |
| Markdown frontmatter | `python-frontmatter` + `ruamel.yaml` for validation/round-tripping | Current PyPI: `python-frontmatter==1.1.0`, `ruamel.yaml==0.19.1` | MEDIUM | Vault pages require YAML frontmatter validation and Obsidian-compatible markdown. Use `ruamel.yaml` when preserving ordering/comments matters; use `python-frontmatter` for simple parse/write if it passes fixture tests. |
| Token estimation | `tiktoken` plus provider-reported usage | Current PyPI: `0.12.0`; depend on `tiktoken>=0.12,<1` as optional/cost extra | MEDIUM | OpenRouter/provider usage is authoritative when present. Static fallback pricing and token estimation are still needed for pre-call budget checks and providers without cost fields. |
| Testing | pytest, pytest-asyncio, respx, hypothesis | Current PyPI: pytest `9.0.3`, pytest-asyncio `1.3.0`, respx `0.23.1`, hypothesis `6.152.3` | HIGH | Needed for deterministic rules replay, HTTP provider contract tests, Textual async tests, schema round-trips, and property tests for PF2e degree-of-success boundaries. |
| Lint/type/security | ruff, pyright, pre-commit, gitleaks | Current PyPI: ruff `0.15.12`, pyright `1.1.409`, pre-commit `4.6.0`; gitleaks external | HIGH | Already installed globally per project. Add project config so CI/local contributors get the same checks. Pyright is important because LangGraph state and Pydantic model boundaries will otherwise drift. |

## Supporting Libraries

### Recommended runtime dependencies

| Package | Version guidance | Confidence | Use | Notes |
|---|---|---:|---|---|
| `langgraph` | `>=1.1,<2` | HIGH | Graph orchestration, typed state flow, routing, streaming. | Compile graphs with a SQLite checkpointer and stable `thread_id` per campaign/session. |
| `langgraph-checkpoint-sqlite` | `>=3,<4` | HIGH | Local durable checkpoints. | Use `SqliteSaver` for LangGraph state, but do not let it obscure SagaSmith's turn-close write ordering. |
| `textual` | `>=8,<9` | HIGH | TUI application. | Use Textual widgets/screens for narration, status panel, input prompt, dice overlay, safety bar, and settings dialogs. |
| `typer` | `>=0.25,<1` | HIGH | CLI entrypoint. | `ttrpg play` should launch the Textual app; admin/repair commands can remain plain CLI. |
| `pydantic` | `>=2.13,<3` | HIGH | Runtime/domain/LLM schemas. | Use strict validation for persisted objects and LLM JSON outputs. Generate JSON Schema from the same models used at runtime. |
| `pydantic-settings` | `>=2.14,<3` | HIGH | Typed dev/app configuration. | Keep campaign/user settings in SQLite; use this mostly for env overrides and internal config. |
| `httpx` | `>=0.28,<1` | HIGH | OpenRouter/direct provider transport. | Use explicit timeouts, response hooks, streaming line parsing, retries owned by provider layer. |
| `keyring` | `>=25,<26` | HIGH | OS credential storage. | Provide env-var fallback for developers and CI; never serialize key values into models. |
| `platformdirs` | `>=4,<5` | HIGH | App data/cache/config paths. | Use for master vault, campaign DB defaults, LanceDB storage, logs. |
| `lancedb` | `>=0.30,<1` | HIGH | Embedded vector/hybrid retrieval. | Put behind `MemoryIndex` interface; first slice may stub until Archivist retrieval lands. |
| `networkx` | `>=3.6,<4` | HIGH | Vault relationship graph. | Store graph as derived in-memory/rebuildable artifact; optionally persist a simple edge cache in SQLite. |
| `python-frontmatter` | `>=1.1,<2` | MEDIUM | Markdown frontmatter parsing. | Good ergonomic default; verify it preserves enough formatting for Obsidian fixtures. |
| `ruamel.yaml` | `>=0.19,<1` | MEDIUM | YAML validation/round-trip control. | Use for stricter frontmatter handling and stable output formatting if `python-frontmatter` is too lossy. |
| `anyio` | `>=4,<5` | MEDIUM | Async coordination. | Textual and HTTPX can coexist cleanly with async helpers; keep deterministic services sync where simpler. |
| `tiktoken` | `>=0.12,<1` | MEDIUM | Token estimation fallback. | Treat estimates as approximate. Provider-reported usage/cost wins. |

### Recommended development dependencies

| Package/tool | Version guidance | Confidence | Use |
|---|---|---:|---|
| `pytest` | `>=9,<10` | HIGH | Unit/integration/eval smoke tests. |
| `pytest-asyncio` | `>=1.3,<2` | HIGH | Textual async tests and async provider tests. |
| `respx` | `>=0.23,<1` | HIGH | Mock HTTPX/OpenRouter calls without real credentials. |
| `hypothesis` | `>=6.152,<7` | HIGH | PF2e rules property tests: degree boundaries, RNG replay, action economy invariants. |
| `ruff` | `>=0.15,<1` | HIGH | Format/lint/import sorting. |
| `pyright` | `>=1.1.409,<2` | HIGH | Static typing. Configure strict mode for core packages. |
| `pre-commit` | `>=4.6,<5` | HIGH | Local quality gate. |
| `textual-dev` | External/dev tool | MEDIUM | Textual live development and debugging. |
| `gitleaks` | External/dev tool | HIGH | Secret scanning, especially for BYOK workflows. |

### Suggested `pyproject.toml` dependency shape

```toml
[project]
name = "ai-sagasmith"
requires-python = ">=3.12,<3.14"
dependencies = [
  "langgraph>=1.1,<2",
  "langgraph-checkpoint-sqlite>=3,<4",
  "textual>=8,<9",
  "typer>=0.25,<1",
  "rich>=15,<16",
  "pydantic>=2.13,<3",
  "pydantic-settings>=2.14,<3",
  "httpx>=0.28,<1",
  "keyring>=25,<26",
  "platformdirs>=4,<5",
  "lancedb>=0.30,<1",
  "networkx>=3.6,<4",
  "python-frontmatter>=1.1,<2",
  "ruamel.yaml>=0.19,<1",
  "anyio>=4,<5",
]

[project.optional-dependencies]
cost = ["tiktoken>=0.12,<1"]
dev = [
  "pytest>=9,<10",
  "pytest-asyncio>=1.3,<2",
  "respx>=0.23,<1",
  "hypothesis>=6.152,<7",
  "ruff>=0.15,<1",
  "pyright>=1.1.409,<2",
  "pre-commit>=4.6,<5",
]

[project.scripts]
ttrpg = "sagasmith.cli.main:app"
sagasmith = "sagasmith.cli.main:app"
```

Use `uv add`/`uv lock` rather than hand-editing once implementation begins, but this is the intended dependency envelope.

## Version Strategy

1. **Use Python `>=3.12,<3.14` for the first implementation.** Python 3.12 is the safe baseline. Python 3.13 can be allowed only after CI verifies Textual, LangGraph, LanceDB, keyring, and packaging behavior on all supported OSes.
2. **Pin major versions in `pyproject.toml`, pin exact resolved versions in `uv.lock`.** Runtime dependencies should use ranges such as `langgraph>=1.1,<2`; `uv.lock` provides reproducible installs.
3. **Review AI-stack dependencies at every milestone.** LangGraph, provider APIs, and LanceDB move quickly. Use `uv lock --upgrade-package <name>` deliberately, not opportunistically.
4. **Do not pin model IDs in code.** Store model choices in campaign/user config. Provide defaults as data, not constants hardwired into agent code.
5. **Keep provider SDKs optional until justified.** Start with HTTPX. Add `openrouter` or `openai` SDK only if direct HTTP becomes a maintenance burden or a provider feature is hard to implement correctly.
6. **Treat storage schema versions separately from package versions.** Checkpoints and SQLite tables need explicit `schema_version` and app semver fields; migrations must be testable against fixture DBs.
7. **Use dependency groups for heavy/optional capabilities.** Embedding models/rerankers can become extras later; avoid forcing large ML dependencies into the minimal install unless LanceDB embedding integration requires them for the current feature.
8. **Prefer stable public APIs over experimental platform tooling.** LangGraph local server/Studio can be useful during development, but the runtime should embed LangGraph directly inside the TUI/CLI rather than requiring `langgraph dev` or an Agent Server.

## Avoid

| Avoid | Confidence | Why not | Use instead |
|---|---:|---|---|
| FastAPI/server backend for MVP | HIGH | Specs explicitly require local-first CLI/TUI with no server dependency. A backend adds process management, ports, auth, and state split complexity without helping the first playable loop. | Embed services directly in the Python app; Textual owns the UI process. |
| LangGraph Platform / Agent Server as runtime dependency | HIGH | Useful for hosted agents, but conflicts with `pip install` local-first TUI distribution and offline vault ownership. | Directly compile and run LangGraph in-process with SQLite checkpointing. |
| CrewAI, AutoGen/AG2, OpenAI Agents SDK, Claude Agent SDK as orchestrator | HIGH | ADR-0001 already rejected these due to checkpointing, model lock-in, fragmentation, or statefulness gaps. | LangGraph plus first-party Agent Skills adapter. |
| Re-opening Agent Skills SDK adoption immediately | HIGH | ADR-0001 chooses a small first-party adapter first. External SDK should be reconsidered only if the adapter exceeds ~500 LOC or interoperability becomes a real requirement. | Implement `SkillStore`, catalog injection, and `load_skill` tool locally. |
| LangChain provider wrappers as primary LLM abstraction | MEDIUM | They can be convenient but may obscure streaming, usage/cost fields, retries, redaction, and OpenRouter-specific behavior. | SagaSmith-owned `LLMClient` Protocol using HTTPX first. |
| OpenRouter Agent SDK | HIGH | It is TypeScript-oriented and overlaps with LangGraph's accepted orchestration role. | OpenRouter REST API via HTTPX under `LLMClient`. |
| Persisting API keys in SQLite, checkpoints, vaults, transcripts, debug logs | HIGH | Explicitly forbidden by `LLM_PROVIDER_SPEC.md` and a major trust risk. | Store in OS keyring or env var reference only; log redacted metadata. |
| Vector DB as source of truth | HIGH | Specs lock the vault as canonical memory; vector indices must be rebuildable. | Obsidian-compatible master vault + SQLite records as authoritative; LanceDB derived. |
| Neo4j/Kuzu/full graph database in MVP | HIGH | Too heavy for local-first install and out of scope. The project explicitly defers graph DB as a derived-layer option. | NetworkX derived graph for relationship/topology queries. |
| Chroma/FAISS instead of LanceDB | MEDIUM | They can work, but LanceDB is already specified and better fits embedded local tables plus hybrid search without a separate service. | LanceDB behind an interface. |
| SQLModel/ORM as the domain model source of truth | MEDIUM | Domain schemas already belong in Pydantic. ORM models can drift and hide transaction ordering. | Pydantic domain models + explicit persistence mappers; SQLModel only where it reduces simple table boilerplate. |
| Async everywhere | MEDIUM | Deterministic rules, dice, vault transforms, and SQLite transaction ordering are easier to test synchronously. Async should serve streaming/UI/network boundaries, not infect pure services. | Sync deterministic core; async adapters for Textual and HTTP streaming. |
| Bundling full PF2e datasets or non-ORC content | HIGH | `PF2E_MVP_SUBSET.md` requires only ORC-compatible/open content and a narrow rules subset. | Curated local data files with explicit source notes and fixtures. |
| Tactical grid/map dependencies | HIGH | MVP is theater-of-mind only. | Position tags: `close`, `near`, `far`, `behind_cover`. |
| Heavy local LLM/runtime dependencies by default | HIGH | Undermines `pip install` and non-technical local-first usability. | BYOK cloud providers first; optional local provider later. |
| Rich visual/image libraries in MVP | HIGH | Artist/ImageProvider is placeholder-only and image generation is out of scope. | Plain Textual placeholders. |

## Open Questions

1. **LangGraph SQLite transaction integration:** The specs require checkpoint storage inside the turn-close SQLite transaction. Current LangGraph `SqliteSaver` examples use a sqlite connection, but implementation must verify whether SagaSmith can safely share the same transaction/connection or should store checkpoint rows through a coordinated adapter. Confidence: MEDIUM; needs prototype before persistence milestone is locked.
2. **OpenRouter structured-output exact contract:** OpenRouter supports OpenAI-compatible chat completions and documents structured outputs, but provider/model support varies. Implementation must test selected default models for JSON Schema reliability and streaming behavior. Confidence: MEDIUM.
3. **OpenRouter Python SDK maturity:** Current PyPI version is `openrouter==0.9.1`. It may become attractive later, but direct HTTPX is more auditable for MVP. Re-evaluate after the first provider contract tests. Confidence: MEDIUM.
4. **Embedding model packaging:** LanceDB can integrate with embedding registries, but SagaSmith should avoid heavy ML dependencies in the base install. Decide during Archivist implementation whether embeddings are provider-generated, local lightweight, or optional extras. Confidence: MEDIUM.
5. **Markdown parser choice:** `python-frontmatter` is ergonomic but may not preserve formatting/comments exactly enough for Obsidian vault round trips. Validate against seed vault fixtures; switch more logic to `ruamel.yaml` plus custom markdown handling if needed. Confidence: MEDIUM.
6. **Installer/distribution path:** `pipx install ai-sagasmith` is the likely user-facing install path, but Textual/keyring/LanceDB behavior on Windows/macOS/Linux should be tested before release packaging claims. Confidence: MEDIUM.
7. **Cost estimation before calls:** Provider-reported costs are best after calls; hard-stop before the next paid call requires a conservative pre-call estimator. Need model metadata/pricing table update strategy. Confidence: MEDIUM.

## Confidence

| Recommendation area | Confidence | Basis |
|---|---:|---|
| LangGraph as orchestrator | HIGH | Locked by ADR-0001 and verified in current docs for checkpoints, interrupts, and streaming. |
| Textual as MVP UI | HIGH | Locked by project/specs; current docs support TUI widgets, command palette, and test pilot patterns. |
| Pydantic v2 for schemas | HIGH | Locked by specs; current docs verify JSON validation, strict mode, `TypeAdapter`, and schema generation patterns. |
| uv for tooling | HIGH | Locked/preferred by project; current docs verify project init, add, lock, sync, build, publish, and dependency groups. |
| SQLite as local transactional store | HIGH | Locked by persistence spec and fits local-first requirements. Implementation details around LangGraph checkpoint transaction sharing remain MEDIUM. |
| OpenRouter via first-party HTTPX client | HIGH | OpenRouter docs verify REST/OpenAI-compatible API; HTTPX docs verify streaming/timeouts/hooks. SDK avoidance is an implementation judgment. |
| LanceDB as vector layer | HIGH | Locked by specs; current docs verify embedded local connection and vector/FTS/hybrid search. |
| NetworkX as graph layer | HIGH | Locked by specs; current docs verify graph construction and path/topology algorithms. |
| Markdown/frontmatter tooling | MEDIUM | The vault model is locked, but exact parser stack needs fixture validation for formatting and Obsidian compatibility. |
| SQLModel use | MEDIUM | Current and compatible, but should not be overused because SagaSmith needs explicit transaction ordering and Pydantic domain schemas. |
| Exact version ranges | MEDIUM | PyPI versions were current on 2026-04-26; use `uv.lock` for reproducibility and milestone upgrades for fast-moving packages. |

## Sources

- `.planning/PROJECT.md` — locked local-first, Textual, LangGraph, OpenRouter, SQLite/vault/LanceDB/NetworkX, uv constraints.
- `docs/sagasmith/ADR-0001-orchestration-and-skills.md` — accepted LangGraph + Agent Skills decisions and rejected orchestrator alternatives.
- `docs/sagasmith/GAME_SPEC.md` — product/runtime contracts for agents, TUI, memory, safety, save/resume, MVP scope.
- `docs/sagasmith/STATE_SCHEMA.md` — Pydantic/JSON Schema and `SagaState` contracts.
- `docs/sagasmith/PERSISTENCE_SPEC.md` — SQLite, checkpoint, vault, rebuild, transaction ordering contracts.
- `docs/sagasmith/LLM_PROVIDER_SPEC.md` — OpenRouter-first BYOK provider abstraction, streaming, structured JSON, retries, secrets, cost.
- `docs/sagasmith/VAULT_SCHEMA.md` — Obsidian-compatible two-vault memory and derived index contracts.
- `docs/sagasmith/PF2E_MVP_SUBSET.md` — deterministic PF2e subset and rules-data constraints.
- Context7: LangGraph Python docs (`/websites/langchain_oss_python_langgraph`) — checkpointing, `SqliteSaver`, streaming modes, `interrupt()`.
- Context7: Textual docs (`/textualize/textual`) — command palette and async app testing with `run_test()`/pilot.
- Context7: Pydantic docs (`/pydantic/pydantic`) — v2 strict validation, JSON validation, `TypeAdapter`.
- Context7: uv docs (`/astral-sh/uv`) — `uv init`, `uv add`, `uv lock`, `uv sync`, build/publish.
- Context7: LanceDB docs (`/websites/lancedb`) — embedded local connect, vector/FTS/hybrid search, reranking.
- Context7: HTTPX docs (`/encode/httpx`) — streaming, timeouts, event hooks.
- Context7: Typer docs (`/fastapi/typer`) — typed CLI commands/subcommands and Rich integration.
- Context7: NetworkX docs (`/websites/networkx_stable`) — graph/path algorithms.
- Context7: SQLModel docs (`/websites/sqlmodel_tiangolo`) — SQLite model/session patterns.
- OpenRouter official docs: <https://openrouter.ai/docs/quickstart> — REST API, OpenAI-compatible endpoint, Python examples, SDK note.
- PyPI JSON metadata checked 2026-04-26 for current package versions listed above.
