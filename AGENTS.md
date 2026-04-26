# SagaSmith Agent Guide

## Project Context

SagaSmith is a local-first, single-player, AI-run tabletop RPG delivered as a Python CLI/TUI application. The MVP validates a solo Pathfinder 2e campaign loop where AI agents plan and narrate while deterministic services own rules, dice, persistence, safety, cost, secrets, and vault writes.

Core value: a solo player can start, play, quit, and resume an AI-run PF2e campaign where the story adapts to their choices while rules, memory, safety, cost, and persistence remain trustworthy.

## Planning Artifacts

Read these before implementation work:

- `.planning/PROJECT.md` - living project context, constraints, decisions, and scope boundaries.
- `.planning/REQUIREMENTS.md` - v1 requirements and roadmap traceability.
- `.planning/ROADMAP.md` - phase structure and success criteria.
- `.planning/STATE.md` - current phase, progress, and continuity notes.
- `.planning/research/SUMMARY.md` - synthesized research findings and risk gates.

Canonical product specs:

- `docs/specs/GAME_SPEC.md` - product and gameplay contract.
- `docs/specs/ADR-0001-orchestration-and-skills.md` - LangGraph and Agent Skills decision.
- `docs/specs/STATE_SCHEMA.md` - runtime state model contract.
- `docs/specs/PF2E_MVP_SUBSET.md` - first-slice rules scope.
- `docs/specs/PERSISTENCE_SPEC.md` - turn-close, checkpoints, and repair contract.
- `docs/specs/LLM_PROVIDER_SPEC.md` - provider, secrets, streaming, retry, and cost contract.
- `docs/specs/VAULT_SCHEMA.md` - master/player vault memory contract.
- `docs/specs/agents/` - planned agent capability catalogs.
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
