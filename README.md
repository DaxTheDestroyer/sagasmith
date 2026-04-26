# SagaSmith

Local-first, single-player, AI-run tabletop RPG CLI/TUI application (PF2e MVP).

## Status

Phase 1: Contracts, Scaffold, and Eval Spine. Not playable yet. Tracks the GSD roadmap in `.planning/ROADMAP.md`.

## Requirements

- Python `>=3.12,<3.14`
- [`uv`](https://docs.astral.sh/uv/)
- `make` optional

## Install

```bash
uv sync --all-groups
uv run pre-commit install  # optional, one-time per clone
```

## Developer Commands

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

## Run the CLI

```bash
uv run sagasmith version
uv run sagasmith --help
```

## Project Layout

```text
src/sagasmith/
├── app/          # Bootstrap, config, session identity, and dependency wiring.
├── cli/          # Typer command entry points for lifecycle and admin commands.
├── tui/          # Textual widgets, screens, events, and display-only UI state.
├── graph/        # LangGraph orchestration, routing, streaming, and thin nodes.
├── agents/       # Prompts and adapters for SagaSmith agent roles; no disk writes.
├── services/     # Deterministic dice, PF2e rules, command, safety, cost, and validation services.
├── providers/    # Provider-neutral LLM client contracts and OpenRouter/direct-provider adapters.
├── persistence/  # SQLite migrations, repositories, turn-close ordering, and checkpoint wiring.
├── memory/       # Vault IO, player projection, FTS5, LanceDB, NetworkX, and retrieval.
├── schemas/      # Pydantic domain/runtime/provider/agent models and JSON Schema export.
├── evals/        # Deterministic replay, fixtures, safety, memory, cost, and smoke harnesses.
└── skills/       # First-party Agent Skills registry and cross-cutting skill packages.
```

## Planning Artifacts

- `.planning/PROJECT.md` — living project context, constraints, decisions, and scope boundaries.
- `.planning/ROADMAP.md` — phase structure and success criteria.
- `.planning/REQUIREMENTS.md` — v1 requirements and roadmap traceability.
- `.planning/STATE.md` — current phase, progress, and continuity notes.
- `.planning/research/SUMMARY.md` — synthesized research findings and risk gates.
- `docs/specs/` — canonical implementation specs for gameplay, state, persistence, providers, vaults, PF2e scope, and agents.

## Secrets

API keys are never committed. See Phase 2 for keyring/env-reference integration.

## License

TBD
