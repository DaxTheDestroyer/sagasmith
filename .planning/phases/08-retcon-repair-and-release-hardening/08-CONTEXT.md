# Phase 8: Retcon, Repair, and Release Hardening - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 delivers safe last-turn retcon behavior and release hardening for the MVP. The player can retcon a selected completed turn after explicit confirmation, retconned turns are excluded from canonical replay, summaries, memory, vault rebuilds, and player-facing canon, and the release gate proves the full no-paid-call MVP path plus lint, formatting, type checking, tests, smoke, and secret scanning.

Phase 8 does not add new gameplay breadth, new rules systems, GUI/web/mobile frontends, multiplayer, tactical maps, LanceDB activation, callback reachability scoring, master-vault unlock, or full post-MVP canon-conflict classification.

</domain>

<decisions>
## Implementation Decisions

### Retcon Semantics
- **D-01:** `/retcon` does not silently target the latest completed turn. The player chooses from recent eligible completed turns before rollback can proceed.
- **D-02:** Retconned data is retained for audit/debugging and marked with retcon status or equivalent audit metadata. Do not destructively delete turn rows, transcript rows, roll logs, vault audit records, or checkpoints as the primary retcon mechanism.
- **D-03:** Retcon rollback starts from checkpoint rewind. The implementation should restore graph/game state from the prior safe checkpoint or prior completed-turn checkpoint, then repair/rebuild derived outputs from canonical sources.
- **D-04:** If safe rollback data is missing or invalid, block the retcon with clear repair guidance. Do not guess, partially rewrite canon, or continue with best-effort state mutation.

### Confirmation UX
- **D-05:** `/retcon` opens a recent-turn picker showing eligible completed turns. The player selects the turn to retcon before seeing the final confirmation.
- **D-06:** Confirmation requires a typed phrase or turn-specific confirmation token. A simple yes/no prompt is not explicit enough for this destructive-canon operation.
- **D-07:** The confirmation screen shows a concise turn summary plus expected effects: state rewind, affected transcript/mechanics/vault/memory outputs, audit retention, and canonical exclusion after success.
- **D-08:** After a successful retcon, return the player to the prior safe prompt/checkpoint and show a concise completion message. Do not force session exit or require an immediate separate repair flow when the automated repair/rebuild succeeds.

### Canonical Exclusion and Repair
- **D-09:** Retconned turns are excluded from all canonical reads by default: replay, summaries, rolling summaries, memory packets, vault rebuilds, player-vault projection, derived FTS5/graph rebuilds, `/recap`, and future gameplay context. Audit/debug reads may opt in explicitly.
- **D-10:** Enforce canonical exclusion through shared repository/query helpers or equivalent canonical access APIs. Avoid scattered local `status != retconned` filters that can drift across subsystems.
- **D-11:** Vault and derived-layer rebuilds use canonical sources only. Retconned content may remain internally auditable, but canonical master/player vault outputs are rebuilt from non-retconned sources.
- **D-12:** Player-facing history may include a brief spoiler-safe log entry that a retcon occurred, but it must not expose removed canon details, GM-only content, or secret/provider data.

### MVP Smoke and Release Gates
- **D-13:** QA-08 smoke must prove the full no-paid-call MVP path: install/entrypoint, init, configure, onboard, play a skill challenge, play simple combat, quit, and resume.
- **D-14:** Smoke coverage should be layered: detailed in-process pytest/harness checks for observability and at least one shell-level `uv run sagasmith ...` path to prove local entrypoint/install behavior.
- **D-15:** Add or target `make release-gate` as the release-blocking wrapper command. It should run lint, format check, type check, unit/integration tests, MVP smoke, and secret scan.
- **D-16:** Secret scanning is release-blocking. The release gate must include gitleaks or the existing pre-commit gitleaks hook plus redaction canary regressions.

### the agent's Discretion
- Exact status names, migration numbers, repository method names, and TUI widget/modal implementation details.
- Exact typed confirmation phrase, as long as it is turn-specific or explicit enough to avoid accidental confirmation.
- Exact shape of the retcon audit record and whether it is stored as a new table, turn metadata, or safety/control event, as long as retained audit data is not canonical by default.
- Exact split between fast in-process smoke checks and shell-level smoke steps, as long as QA-08 and QA-09 decisions above are satisfied.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning Scope
- `.planning/ROADMAP.md` — Phase 8 goal, requirements, success criteria, and dependency on Phase 7.
- `.planning/REQUIREMENTS.md` — Full text for `QA-01`, `QA-02`, `QA-08`, and `QA-09`.
- `.planning/PROJECT.md` — Trust-before-breadth principle, deterministic-services boundary, local-first constraints, secret-safety requirements, and out-of-scope boundaries.
- `.planning/STATE.md` — Current project progress, Phase 7 status, and deferred integration/release context.

### Prior Phase Context
- `.planning/phases/06-ai-gm-story-loop/06-CONTEXT.md` — Narration recovery decisions, pre-narration checkpoint stability, and Phase 8 retcon deferral.
- `.planning/phases/07-memory-vault-and-resume/07-CONTEXT.md` — Vault source-of-truth, derived-layer rebuild, player-vault sync, and Phase 8/post-MVP deferrals.

### Product and Runtime Specs
- `docs/sagasmith/GAME_SPEC.md` — Core game loop, turn flow, player-facing command behavior, safety, and local-first RPG contract.
- `docs/sagasmith/PERSISTENCE_SPEC.md` — Turn-close ordering, checkpoints, repair, rebuild, and atomic write rules.
- `docs/sagasmith/STATE_SCHEMA.md` — Persisted state, turn/checkpoint/state-delta contracts, and schema-validation expectations.
- `docs/sagasmith/VAULT_SCHEMA.md` — Master/player vault projection, visibility, GM-only stripping, and rebuild implications.
- `docs/sagasmith/PF2E_MVP_SUBSET.md` — Skill challenge and simple combat boundaries for the MVP smoke path.
- `docs/sagasmith/LLM_PROVIDER_SPEC.md` — No-paid-call defaults, provider fake/real boundaries, cost accounting, and secret redaction constraints.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sagasmith/tui/commands/control.py` — `RetconCommand` currently exists as a Phase 8 stub and is the player-facing command replacement point.
- `src/sagasmith/graph/runtime.py` — Existing `discard_incomplete_turn()`, `retry_narration()`, and `_rewind_to_checkpoint()` patterns should guide checkpoint-based retcon rollback.
- `src/sagasmith/persistence/repositories.py` — `TurnRecordRepository.get/upsert` exists; Phase 8 likely adds recent eligible completed-turn and canonical-turn helpers.
- `src/sagasmith/schemas/persistence.py` and `src/sagasmith/persistence/migrations/0006_turn_record_status.sql` — Current turn-status schema/migration surface for adding retcon status or metadata.
- `src/sagasmith/persistence/turn_close.py` — Turn-close source of truth for completed turn persistence and repair ordering.
- `src/sagasmith/agents/archivist/transcript_context.py` — Recent transcript retrieval joins `turn_records`; Phase 8 should route through canonical helpers to exclude retconned turns.
- `src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py` — Memory packet assembly surface that must consume canonical-only transcript/summary/vault data.
- `src/sagasmith/memory/fts5.py`, `src/sagasmith/memory/graph.py`, and `src/sagasmith/vault/__init__.py` — Derived index and player-vault rebuild/sync surfaces that must avoid retconned canon.
- `src/sagasmith/evals/harness.py` and `src/sagasmith/cli/smoke_cmd.py` — Existing smoke harness and CLI smoke command extension points for QA-08.
- `Makefile`, `.pre-commit-config.yaml`, and `.gitleaks.toml` — Existing quality and secret-scan tooling for QA-09 and `make release-gate`.

### Established Patterns
- Runtime/checkpoint boundaries own persistence and recovery; agent nodes stay pure and return state updates only.
- Typed repositories and SQLite migrations are preferred over ad hoc SQL in feature code.
- Existing recovery behavior marks rows/statuses rather than destructively deleting data; retcon should preserve this audit-first pattern.
- TUI commands are registered through `CommandRegistry` and implemented as command objects.
- Tests commonly use in-memory SQLite with `apply_migrations()` and deterministic fake services.
- No-paid-call paths use `DeterministicFakeClient`, smoke fixtures, and `SagaSmithApp.run_test()` for TUI flows.
- Derived vault/search layers are rebuildable from canonical sources; retcon should use rebuild/repair rather than mutating derived artifacts by hand when possible.
- Secret protection uses both in-code `RedactionCanary` checks and external/pre-commit gitleaks scanning.

### Integration Points
- Replace the Phase 8 retcon stub in `src/sagasmith/tui/commands/control.py` with picker, summary/effects display, typed confirmation, and runtime call.
- Add repository/canonical query helpers around `turn_records`, transcript rows, roll logs, summaries, and rebuild inputs.
- Add migration/schema support for retcon status or retcon audit metadata.
- Extend graph runtime checkpoint rewind with a last-selected-completed-turn retcon path distinct from incomplete narration discard/retry.
- Update Archivist memory, `/recap`, vault rebuild, FTS5, and NetworkX rebuild code paths to use canonical-only helpers.
- Extend smoke harness/CLI smoke and add `make release-gate` to compose existing quality commands and new MVP smoke.

</code_context>

<specifics>
## Specific Ideas

- Retcon should feel like a deliberate safety/canon correction tool, not a quick undo key. The recent-turn picker plus typed phrase gives the user control while reducing accidental rollback risk.
- Audit retention matters. Retconned data should be available for debugging and trust, but never fed back into canonical gameplay, summaries, player vaults, or derived memory.
- The release gate should prove the app as a local CLI/TUI product, not just library functions. At least one shell-level `uv run sagasmith ...` path is required for confidence in packaging/entrypoint behavior.

</specifics>

<deferred>
## Deferred Ideas

- Full LLM-based `canon-conflict-detection` classifier — deferred from Phase 7 and still not required for Phase 8 unless separately promoted.
- `callback-reachability-query` — deferred from Phase 7/post-MVP.
- `master-vault-unlock` director's-cut artifact — post-MVP.
- LanceDB semantic search activation — post-MVP or a future hardening phase after embedding cost is accepted.
- New gameplay breadth beyond retcon and release-hardening flows — out of scope for Phase 8.

</deferred>

---

*Phase: 08-retcon-repair-and-release-hardening*
*Context gathered: 2026-04-29*
