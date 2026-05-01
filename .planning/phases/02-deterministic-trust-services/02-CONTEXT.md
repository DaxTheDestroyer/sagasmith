# Phase 2: Deterministic Trust Services - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers deterministic trust services before gameplay: provider and cost boundaries, secret-safe logging, seeded dice and PF2e degree-of-success primitives, SQLite trust records, transaction ordering, replayable state deltas, and privacy gates. It does not deliver TUI setup, onboarding, graph orchestration, player-facing gameplay, full PF2e skill/combat resolution, vault writes, derived memory indices, or player-vault sync.

</domain>

<decisions>
## Implementation Decisions

### Provider Boundary
- **D-01:** Real OpenRouter calls are implemented but verification is opt-in only. Default tests, smoke checks, and CI paths must use deterministic mocks/fakes and make no paid calls.
- **D-02:** The first `LLMClient` implementation covers both non-streaming structured JSON calls and streaming text calls because Phase 2 owns PROV-03 and PROV-04, and later Orator work must use the same abstraction.
- **D-03:** JSON schema failures follow the `LLM_PROVIDER_SPEC.md` retry ladder: one same-model repair, one cheap-model repair, then fail the node/service with redacted metadata.
- **D-04:** Provider logs are metadata-first. Persist provider/model/agent/turn/request IDs, failure kind, retry count, usage, cost, and safe redacted snippets or hashes at most; do not persist full prompt/response bodies in Phase 2 provider logs.

### Secret Handling
- **D-05:** Phase 2 supports OS keyring references and environment-variable references only. Plaintext API keys and encrypted local config files are out of scope for this phase.
- **D-06:** Secret leakage gates fail closed. Tests and runtime write/log gates must reject artifacts containing secret-shaped text unless the value has already been replaced by a safe redaction marker.
- **D-07:** Redaction canary coverage applies to all trust artifacts touched in Phase 2: provider logs, cost logs, checkpoint/state dumps, transcripts or transcript-like records, SQLite test exports, generated schemas, and smoke output.
- **D-08:** Missing or invalid credential references surface as SagaSmith-owned typed errors containing only safe provider/ref-kind information. Errors must never echo env var values, key contents, or authorization headers.

### Cost Accounting
- **D-09:** When provider-reported cost is missing, CostGovernor uses a bundled static pricing table by provider/model and marks the cost approximate.
- **D-10:** Pre-call budget checks use worst-case estimates based on prompt tokens plus configured `max_tokens`. A paid call is blocked before execution if the worst-case estimate would exceed the session budget.
- **D-11:** The 70% and 90% warnings fire exactly once after a cost update crosses each threshold, and the warning state is persisted in `CostState.warnings_sent`.
- **D-12:** A budget hard stop returns or raises a typed budget-stop result containing safe user-facing text and updated cost state. It must not make a provider call or create provider-side side effects.

### Persistence and Rules Boundary
- **D-13:** Phase 2 stops PF2e rules scope at seeded d20/DiceService replay and PF2e degree-of-success math. Fixed-DC skill checks, Strikes, initiative, HP damage application, action economy, and combat flow remain Phase 5 work.
- **D-14:** Dice replay uses a campaign/session seed plus ordered roll index and roll purpose/input. The same seed and same ordered inputs must reproduce the same roll results without serializing RNG internals.
- **D-15:** Phase 2 persistence scope is SQLite trust records: migrations/repositories for turn records, roll logs, state deltas, provider logs, cost logs, checkpoint references, and transaction ordering. Real vault writes, derived indices, and player-vault sync remain later phases.
- **D-16:** Fold all relevant Phase 1 advisory hardening into Phase 2 planning: enforce `current_hp <= max_hp` where HP schemas are consumed, add `sk-proj-` and related provider-key canary coverage, validate fixture overrides instead of bypassing validation, and keep source pyright strictness visible.

### the agent's Discretion
- Planner may choose exact module names, repository abstractions, migration tooling, fake-provider shape, static pricing table format, and typed exception/result class names as long as the decisions above and canonical specs are followed.
- Planner may decide whether redacted snippets are stored at all; full prompt/response bodies are not stored in Phase 2 provider logs.
- Planner may choose whether SQLite trust records are exposed only through repositories or also through small service APIs, provided transaction ordering and testability stay explicit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning Scope
- `.planning/ROADMAP.md` — Phase 2 goal, dependencies, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — PROV-01 through PROV-06, COST-01 through COST-05, RULE-01 through RULE-03, PERS-01/PERS-02/PERS-04, QA-04, and QA-07 mappings.
- `.planning/PROJECT.md` — product constraints, local-first rules, OpenRouter-first decision, deterministic-services principle, and out-of-scope boundaries.
- `.planning/STATE.md` — current Phase 2 focus and Phase 1 advisory hardening items to fold into planning.

### Product and Runtime Specs
- `docs/sagasmith/GAME_SPEC.md` — core product contract for provider, cost, DiceService, turn flow, safety, and local-first boundaries.
- `docs/sagasmith/LLM_PROVIDER_SPEC.md` — `LLMClient` protocol, request/response/event fields, model config, retry ladder, cost accounting, streaming, and secrets requirements.
- `docs/sagasmith/PERSISTENCE_SPEC.md` — SQLite-first turn lifecycle, checkpoint behavior, transaction ordering, and later vault/derived-layer boundaries.
- `docs/sagasmith/PF2E_MVP_SUBSET.md` — deterministic rules source of truth, degree-of-success math, seeded dice replay, and first-slice boundaries.
- `docs/sagasmith/STATE_SCHEMA.md` — existing schema contracts for `SagaState`, `CostState`, `RollResult`, `CheckResult`, `StateDelta`, and related persisted/LLM-boundary models.

### Phase 1 Continuity
- `.planning/phases/01-contracts-scaffold-and-eval-spine/01-VERIFICATION.md` — validated Phase 1 artifacts and advisory residual risks for Phase 2 hardening.
- `.planning/phases/01-contracts-scaffold-and-eval-spine/01-02-SUMMARY.md` — schema model, validation gate, and JSON Schema export patterns.
- `.planning/phases/01-contracts-scaffold-and-eval-spine/01-03-SUMMARY.md` — no-paid-call smoke spine, redaction canary, fixture, and smoke harness patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sagasmith/schemas/*` — strict Pydantic v2 contracts already define `CostState`, `RollResult`, `CheckResult`, `StateDelta`, `SagaState`, and related boundary models for deterministic services to consume or extend.
- `src/sagasmith/schemas/validation.py` — persisted-state validation already translates Pydantic validation failures into a SagaSmith-owned `PersistedStateError`; Phase 2 typed trust-service errors should follow this pattern.
- `src/sagasmith/evals/redaction.py` — `RedactionCanary` exists with provider/header-shaped secret scanning and should be expanded for Phase 2 provider-key coverage.
- `src/sagasmith/evals/harness.py` — `run_smoke()` and stable `SmokeCheck` names provide the pattern for adding critical Phase 2 smoke checks.
- `src/sagasmith/evals/fixtures.py` — deterministic fixture factories exist, but Phase 2 should harden override validation when adding trust-service fixtures.
- `src/sagasmith/cli/main.py` — Typer command registration is established for `schema`, `smoke`, and `version`; Phase 2 may add no-paid-call inspection commands only if needed for service verification.

### Established Patterns
- All boundary schemas inherit `SchemaModel` with `extra="forbid"` and `strict=True`; deterministic services should fail closed at model boundaries.
- Persisted JSON-compatible string values use `Literal[...]` fields while enum classes remain shared vocabulary.
- Generated JSON Schema files are reproducible artifacts, not committed outputs.
- Smoke checks are provider-free, synchronous, deterministic, and named for CI triage.
- The package layout already reserves `providers`, `services`, and `persistence` subpackages for Phase 2 implementation.

### Integration Points
- `src/sagasmith/providers/` is the natural home for `LLMClient`, request/response/event models, OpenRouter client, and deterministic fake clients.
- `src/sagasmith/services/` is the natural home for CostGovernor, DiceService, PF2e degree-of-success math, and privacy/secret gates that are not provider-specific.
- `src/sagasmith/persistence/` is the natural home for SQLite migrations/repositories, trust records, transaction ordering, and checkpoint references.
- `src/sagasmith/evals/` and `tests/evals/` should gain Phase 2 smoke and regression coverage for no-paid-call provider fakes, redaction, cost thresholds, seeded replay, and SQLite transaction invariants.

</code_context>

<specifics>
## Specific Ideas

- Default verification must remain no-paid-call. Live OpenRouter checks are explicit opt-in only.
- Provider logs should be useful for audit and cost accounting without becoming transcript storage or prompt archives.
- Redaction is not just cosmetic: leakage detection should block writes/logging unless values are already safely redacted.
- Cost hard stops should be service-level typed results now so Phase 3 TUI and Phase 4 graph interrupts can route them cleanly later.
- Rules planning must avoid pulling Phase 5 skill/combat mechanics into Phase 2; prove the replay and degree primitives first.

</specifics>

<deferred>
## Deferred Ideas

- Full fixed-DC skill checks, Strike resolution, initiative ordering, HP damage application, action economy, and simple combat flow — Phase 5.
- TUI `/budget`, player-facing budget panels, and setup prompts for credentials or budgets — Phase 3.
- LangGraph interrupts and provider/cost node routing — Phase 4.
- Master-vault atomic writes, derived indices, player-vault projection, and repair commands — Phase 7.
- Encrypted local config for API keys — not required for MVP Phase 2; keyring and env-var references are enough.
- Direct provider implementations beyond OpenRouter — supported by the abstraction later, not required as first Phase 2 implementation.

</deferred>

---

*Phase: 02-deterministic-trust-services*
*Context gathered: 2026-04-26*
