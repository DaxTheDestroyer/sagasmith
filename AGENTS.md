# SagaSmith Agent Guide

## Project Context

SagaSmith is a local-first, single-player, AI-run PF2e tabletop RPG (Python CLI/TUI).
For full product/runtime context, see `docs/sagasmith/SAGASMITH_CONTEXT.md`.

## Hard Context Separation

See `LAYOUT.md` for a visual map of the two harnesses.

- Root `CONTEXT.md` is coding-harness routing only. It is not SagaSmith product/runtime context.
- `CONTEXT-MAP.md` documents where each context lives, but this `AGENTS.md` section is the workspace rule agents must obey.
- SagaSmith product/runtime context belongs in `docs/sagasmith/SAGASMITH_CONTEXT.md` and accepted SagaSmith specs/ADRs.
- Coding-harness notes, Kilo/GSD workflow decisions, skill outputs, and architecture-review backlog belong in `.kilo/`, root harness docs, or planning artifacts unless the user explicitly promotes them into a SagaSmith spec or ADR.
- SagaSmith runtime agents and game code must not read root `CONTEXT.md`, `CONTEXT-MAP.md`, `.kilo/`, `.kilocode/`, or `.planning/` as campaign, game-world, player-facing, or in-world context.
- Coding-harness agents may inspect SagaSmith specs and code to do implementation work, but must not treat harness files as SagaSmith runtime truth.
- The boundary is enforced by `tests/architecture/test_harness_separation.py`.

## Planning Artifacts

Read these before implementation work:

- `.planning/PROJECT.md` - living project context, constraints, decisions, and scope boundaries.
- `.planning/REQUIREMENTS.md` - v1 requirements and roadmap traceability.
- `.planning/ROADMAP.md` - phase structure and success criteria.
- `.planning/STATE.md` - current phase, progress, and continuity notes.
- `.planning/research/SUMMARY.md` - synthesized research findings and risk gates.

Canonical product specs:

- `docs/sagasmith/SAGASMITH_CONTEXT.md` - SagaSmith-owned product/runtime context and domain vocabulary.
- `docs/sagasmith/GAME_SPEC.md` - product and gameplay contract.
- `docs/sagasmith/ADR-0001-orchestration-and-skills.md` - LangGraph and Agent Skills decision.
- `docs/sagasmith/STATE_SCHEMA.md` - runtime state model contract.
- `docs/sagasmith/PF2E_MVP_SUBSET.md` - first-slice rules scope.
- `docs/sagasmith/PERSISTENCE_SPEC.md` - turn-close, checkpoints, and repair contract.
- `docs/sagasmith/LLM_PROVIDER_SPEC.md` - provider, secrets, streaming, retry, and cost contract.
- `docs/sagasmith/VAULT_SCHEMA.md` - master/player vault memory contract.
- `docs/sagasmith/agents/` - planned agent capability catalogs.
- `docs/WISHLIST.md` - deferred and explicitly post-MVP features.

## Current Roadmap

Phase 1 is ready for planning: Contracts, Scaffold, and Eval Spine.

Planned phases:

1. Contracts, Scaffold, and Eval Spine
2. Deterministic Trust Services
3. CLI Setup, Onboarding, and TUI Controls
4. Graph Runtime and Agent Skills
5. Rules-First PF2e Vertical Slice
6. AI GM Story Loop
7. Memory, Vault, and Resume Differentiator
8. Retcon, Repair, and Release Hardening

Use `/gsd-plan-phase 1` to begin execution planning.

## Engineering Rules

- Trust-before-breadth: deterministic contracts, tests, persistence, safety, cost, and replay come before richer AI behavior.
- LLM agents propose, plan, summarize, and narrate; deterministic services validate, resolve, persist, account, write, and enforce.
- The deterministic PF2e engine is the source of truth for modifiers, DCs, damage, HP changes, action counts, degree-of-success outcomes, and roll logs.
- The vault is the source of truth for campaign canon; SQLite, FTS5, LanceDB, and NetworkX are supporting or derived layers.
- The player vault is a spoiler-safe projection. Never expose master-vault GM-only content during active campaigns.
- API keys and auth headers must never appear in campaign files, vaults, transcripts, checkpoints, logs, or generated artifacts.
- Avoid scope creep into GUI, multiplayer, tactical maps, image generation, standalone deferred agents, multiple rules systems, or high-level PF2e until the roadmap explicitly promotes them.

## Workflow

- Follow `.planning/ROADMAP.md` phase order unless the user explicitly changes priorities.
- Before implementing a phase, run `/gsd-plan-phase <phase>`.
- Treat `.planning/REQUIREMENTS.md` IDs as the traceability source for implementation and verification.
- Update `.planning/STATE.md` only through GSD phase transitions or explicit planning workflow updates.
- Keep coding-harness context separate from SagaSmith product/runtime context: root `CONTEXT.md` is harness routing only; SagaSmith context belongs in `docs/sagasmith/SAGASMITH_CONTEXT.md`.
- Preserve existing user changes. Do not revert unrelated work.

## Quality Gates

Phase work should include relevant verification for the touched area. The eventual release gate requires:

- Lint and format checks.
- Type checking.
- Unit tests.
- No-paid-call smoke tests.
- Secret scanning.
- Rules replay and PF2e mechanics tests.
- Safety redline regression.
- Player-vault GM-only leakage regression.
- CostGovernor warning and hard-stop regression.
