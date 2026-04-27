---
phase: 2
reviewers: [gemini, claude, codex, opencode]
reviewed_at: 2026-04-26T20:06:59.8937468-06:00
plans_reviewed:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
  - 02-05-PLAN.md
  - 02-06-PLAN.md
---

# Cross-AI Plan Review — Phase 2

Phase 2 review prompt was sent to available external CLIs detected on this machine: Gemini, Claude, Codex, and OpenCode. Gemini, Claude, and OpenCode returned review feedback. Codex was detected but failed due local account/model compatibility errors and is included below as an invocation failure record rather than review feedback.

## Gemini Review

Here is a comprehensive review of the Phase 2 implementation plans for SagaSmith.

### 1. Overall Summary
The Phase 2 plans are exceptionally well-structured, tightly scoped, and rigorously aligned with the architectural principles outlined in `PROJECT.md` and `CONTEXT.md`. The division of labor across the 6 plans is logical, progressing from pure offline primitives (secrets, dice, schemas) to orchestrator-ready services (cost, provider) and finally persistence. The strict adherence to the "fail closed" philosophy for secrets, budgets, and state invariants is a standout characteristic of this phase.

### 2. Plan-by-Plan Analysis

#### 02-01-PLAN.md (SecretRef, Redaction, Errors, HP Invariant)
* **Summary**: Establishes foundational security types, expands the redaction canary to cover modern OpenAI keys, and patches a Phase 1 HP invariant advisory.
* **Strengths**:
  * Excellent use of Pydantic model validators to enforce invariants (`current_hp <= max_hp`).
  * `SecretRef` safely encapsulates credential retrieval without leaking values into memory permanently.
  * Threat model explicitly addresses exception-flow leakage (T-02-01, T-02-02).
* **Concerns**:
  * **LOW**: The plan introduces `keyring` as a runtime dependency. On headless Linux CI environments, `keyring` can fail unpredictably if DBus or Secret Service is missing. While tests monkeypatch it, a developer running the app locally without a configured OS keychain might encounter opaque errors.
* **Suggestions**:
  * Ensure `SecretRefError` provides actionable advice if the underlying `keyring` backend raises a `keyring.errors.KeyringError` (e.g., "OS keychain unavailable").

#### 02-02-PLAN.md (DiceService & PF2e Math)
* **Summary**: Introduces seeded, deterministic d20 rolling and pure PF2e degree-of-success calculations.
* **Strengths**:
  * The cryptographic hashing approach (`hashlib.sha256`) guarantees absolute cross-platform determinism, avoiding Python's `random` module drift.
  * TDD behavior cases comprehensively cover all natural 1/20 adjustment edges.
* **Concerns**:
  * None. This is a perfectly scoped and mathematically sound plan.
* **Suggestions**:
  * None required.

#### 02-03-PLAN.md (LLMClient, Fake, Retry Ladder, Logs)
* **Summary**: Defines the model-agnostic `LLMClient` protocol, a robust retry ladder (`invoke_with_retry`), metadata-only logging, and a deterministic fake client.
* **Strengths**:
  * The `DeterministicFakeClient` completely isolates the test suite from network flakiness and paid calls.
  * Redaction integration directly into `build_provider_log_record` ensures secrets never reach the SQLite layer.
* **Concerns**:
  * **MEDIUM**: The plan specifies that `invoke_with_retry` wraps `client.complete(request)`. It does not mention wrapping `client.stream(request)`. `LLM_PROVIDER_SPEC.md` states: *"If the stream fails mid-turn, the transcript records a failed generation event and the graph retries or falls back..."* It is ambiguous whether streaming retries are handled by this Phase 2 service or deferred entirely to the Phase 4/6 graph logic.
* **Suggestions**:
  * Explicitly document in the plan whether `invoke_with_retry` is expected to support streams, or state that streaming failure recovery is the responsibility of the LangGraph runtime.

#### 02-04-PLAN.md (CostGovernor & Pricing)
* **Summary**: Implements session budget tracking, provider/static pricing, and a pre-flight block for over-budget calls.
* **Strengths**:
  * `BudgetStopResult` is a clean, immutable contract that isolates state mutation from enforcement.
  * Handling of unknown costs (treating as $0.00 approximate) prevents the engine from hard-crashing during development if a new model is tested before the static table is updated.
* **Concerns**:
  * **LOW**: The pricing table is bundled as a static JSON file. OpenRouter prices fluctuate frequently.
* **Suggestions**:
  * Ensure `load_pricing_table` fails gracefully or defaults to a safe fallback if the JSON file structure is accidentally malformed in the future.

#### 02-05-PLAN.md (OpenRouterClient & Transport)
* **Summary**: Delivers the real OpenRouter implementation using `httpx` behind an injectable `HttpTransport` interface.
* **Strengths**:
  * Transport injection (`HttpTransport`) is a textbook application of dependency inversion, making the provider client trivially testable.
  * API keys are resolved at the last possible microsecond and dropped immediately.
* **Concerns**:
  * **MEDIUM**: Server-Sent Events (SSE) parsing can be brittle. While `httpx.iter_lines()` handles TCP buffering, `json.loads(choice["delta"])` might throw a `JSONDecodeError` if the provider sends a malformed chunk.
* **Suggestions**:
  * Add a specific test case for malformed JSON chunks in the SSE stream to ensure they yield a `FailedEvent` rather than crashing the Python generator.

#### 02-06-PLAN.md (SQLite Trust Records & Turn Close)
* **Summary**: Creates the SQLite persistence layer, schema migrations, repositories, and the atomic `close_turn` manager.
* **Strengths**:
  * Strict transaction boundaries ensure a turn is never partially committed.
  * `RedactionCanary` integration into the table-dump tests (QA-04) provides incredible defense-in-depth against secret leakage.
* **Concerns**:
  * **HIGH (Contradiction)**: `STATE.md` explicitly lists a key decision: `[02-06]: SQLite implicit transaction semantics replace explicit BEGIN in close_turn to avoid "cannot start a transaction within a transaction".` However, the execution instructions in `02-06-PLAN.md` explicitly state: `1. conn.execute("BEGIN") (explicit, do not rely on implicit).` Python's `sqlite3` module auto-starts transactions by default (unless `isolation_level=None`); running `BEGIN` manually will throw an OperationalError.
* **Suggestions**:
  * Update `02-06-PLAN.md` Task 2 to remove `conn.execute("BEGIN")`, aligning with the `STATE.md` architectural decision and Python's default `sqlite3` behavior.

### 3. Overall Risk Assessment

**Risk Level: LOW**

The Phase 2 plans are robust, modular, and highly testable. The primary risk lies in the specific SQLite transaction conflict highlighted in Plan 06, which will cause test failures during execution if not resolved. Aside from that contradiction, the designs for secret handling, cost governance, and provider abstraction are exceptional and perfectly positioned to support the LangGraph implementation in Phase 4.

---

## the agent Review

# Cross-AI Plan Review: SagaSmith Phase 2 — Deterministic Trust Services

**Reviewer:** Claude Opus 4.7
**Reviewed:** 2026-04-26
**Plans:** 02-01 through 02-06 (6 plans, 4 waves)
**Phase status (per STATE.md):** Already executed and complete — review is retrospective/educational

---

## Context

These six plans deliver the deterministic-services trust spine for SagaSmith before any LLM gameplay turns on: typed errors and secret references, seeded dice + PF2e degree math, the `LLMClient` abstraction with retry ladder, `CostGovernor`, the real OpenRouter client, and the SQLite turn-records persistence layer. They are sequenced in 4 waves with explicit `depends_on` chains and a single shared smoke-check counter (7 → 8 → 10 → 11) plus schema-export counter (16 → 20 → 25) that thread through them.

The plans are above-average in rigor: STRIDE registers per plan, explicit interface blocks pulled from canonical specs, file-modification contracts in frontmatter, and (where TDD-tagged) explicit RED/GREEN test enumeration. Most concerns below are about **cross-plan contracts**, **silent-fail tradeoffs**, and a few **known-buggy patterns** that the executor presumably adapted around at runtime.

---

## Plan 02-01 — Errors + SecretRef + Redaction + HP invariant

### Summary
Foundation plan for Wave 1: typed `TrustServiceError` hierarchy, `SecretRef` resolver against keyring/env, `RedactionCanary` extension for `sk-proj-` keys, and the deferred Phase 1 HP invariant. Pre-creates `BudgetStopError` and `ProviderCallError` as placeholders so downstream plans don't fight over `errors.py`.

### Strengths
- Pre-creating placeholder exception classes avoids `errors.py` merge conflicts in later waves.
- `SecretRefError.__str__` is carefully bounded — only provider/ref_kind/reason, never the secret value.
- `_with_overrides` re-validation fix closes a real Phase 1 gap (Pydantic `model_copy(update=...)` bypasses validators).
- Locked label inventory test means future canary changes are explicit, not silent.

### Concerns
- **MEDIUM — Regex priority assumption:** The plan inserts `openai_project_key` *before* `openai_key` and asserts the test that `sk-proj-...` does NOT also produce an `openai_key` hit. This requires `RedactionCanary.scan()` to either dedupe overlapping matches by index or stop after first label. Phase 1's existing scanner returns *all* hits — if it doesn't dedupe by span, both labels will fire and the test fails. The plan should explicitly inspect the existing scan implementation and either confirm dedup or change the regex (`sk-(?!proj-)[A-Za-z0-9]{20,}` for the generic key).
- **MEDIUM — `resolve_secret(provider="<unknown>")`:** Provider context is known to every caller (Plan 05 always knows it's `"openrouter"`). Hardcoding `"<unknown>"` in error messages loses useful triage info. Add a `provider: str` parameter; SecretRefError is already designed to carry it.
- **LOW — `keyring>=24,<26` cross-platform footprint:** On Linux this pulls libsecret + dbus, complicating local-first `pip install`. Document the platform expectations or fall back to env-only on minimal systems.
- **LOW — `SecretRef.name` not validated non-empty:** Strict mode catches type mismatches but `name=""` would slip through and produce confusing keyring/env errors at resolve time.

### Suggestions
- Verify `RedactionCanary.scan` dedup behavior in source before relying on label-priority ordering, OR rewrite `openai_key` regex with a negative lookahead.
- Add `provider: str` parameter to `resolve_secret` so error messages carry real context.
- Add `min_length=1` to `SecretRef.name`.

### Risk: **LOW–MEDIUM**
Mostly bounded scope. Regex priority is the only thing likely to fail at execution.

---

## Plan 02-02 — DiceService + compute_degree (TDD)

### Summary
Two pure-functional primitives delivered through proper RED/GREEN/REFACTOR: PF2e degree math and a hash-derived seeded dice service. Cleanly avoids any RNG state serialization.

### Strengths
- Hash-derived determinism (`sha256(seed|...|index)`) is elegant — no RNG state to checkpoint, perfect replay semantics, no cross-process drift.
- 14 explicit boundary cases for `compute_degree` cover every ±10 edge × natural 1/20 combination.
- Frozen dataclass for `DiceService` prevents seed mutation mid-session.
- Explicitly avoids touching `services/__init__.py` (Plan 01's territory) — good parallel-safety hygiene.

### Concerns
- **LOW — Modulo bias on `(n % sides) + 1`:** Negligible for d20 (2^64 % 20 bias is tiny), but if `roll(die="d1000")` is ever exercised the bias becomes measurable. Documented limit (sides ≤ 1000) makes this acceptable.
- **LOW — `DiceService` not re-exported:** Plan defers package-level export; Phase 5 will need to import from `sagasmith.services.dice` directly. Minor friction, not a defect.
- **LOW — `compute_degree` is d20-specific but unnamed as such:** A future `compute_dN_degree` for non-d20 dice would collide. Naming `compute_d20_degree` upfront would be clearer; trivial concern.

### Suggestions
- Add a `// PHASE-NOTE: d20 only; future dice may need a parameterized variant` comment.
- Confirm Plan 03 or 05 re-exports `DiceService` from `services/__init__.py` so Phase 5 doesn't need to know module layout.

### Risk: **LOW**
Pure functions, full TDD coverage, no integration surface. This is the cleanest plan in the wave.

---

## Plan 02-03 — LLMClient Protocol + Retry Ladder + Fake (TDD)

### Summary
Wave 2 anchor: defines the `LLMClient` Protocol, typed request/response/event models, the D-03 retry ladder via `invoke_with_retry`, the metadata-only `build_provider_log_record`, and the `DeterministicFakeClient` that keeps every downstream test offline.

### Strengths
- Tagged union (`kind` discriminator) for `LLMStreamEvent` is the right Pydantic v2 pattern.
- Per-attempt logging (4 records on full ladder exhaustion) gives audit trail for retry behavior.
- Snippet/hash split in log records (snippet only when canary clean, hash always) is good defense-in-depth.
- Test for `no network imports in fake.py` is a nice structural assertion.

### Concerns
- **HIGH — Cross-plan exception contract gap:** `invoke_with_retry` checks `client.complete raising a typed exception with .failure_kind`, but Plan 02-03 doesn't define a base class for transport-level exceptions. Plan 02-05 invents `_OpenRouterError` with that attribute. **There is no shared interface guaranteeing this attribute exists.** A future provider that raises a stdlib `TimeoutError` would bypass the ladder entirely. Define `class ProviderTransportError(Exception): failure_kind: Literal[...]` here in Plan 02-03 and require Plan 05 to subclass it.
- **MEDIUM — `request_with_repair_hint` is unspecified:** The plan mentions wrapping the second attempt with a "repair hint" but provides no concrete shape (extra system message? appended user turn? `metadata` flag?). Implementer is guessing. Specify exactly what gets added to the request on attempt 2.
- **MEDIUM — `jsonschema>=4.20,<5` is heavy:** Pydantic already ships with a JSON Schema validator (`TypeAdapter` or `Validator`). Adding `jsonschema` doubles validation surface area for one feature. Consider Pydantic-only.
- **LOW — `parsed_json: dict | list | None`:** Excludes scalar JSON (`true`, `42`, `"string"`). Valid in spec but rare. Acceptable.
- **LOW — `LLMRequest.metadata: dict[str, str]`:** Stringly-typed metadata dict has poor pyright ergonomics; downstream agents will want richer typing.

### Suggestions
- **Add `ProviderTransportError` base class with `failure_kind` attribute in Plan 02-03; require Plan 05's `_OpenRouterError` to subclass it.**
- Specify the exact shape of `request_with_repair_hint` (e.g., "append assistant message with raw failed output, then user message with `'Repair this JSON to match the schema strictly.'`").
- Evaluate dropping `jsonschema` in favor of `pydantic.TypeAdapter(dict).json_schema()` validation.

### Risk: **MEDIUM**
The exception-contract gap is real and will surface as soon as a second provider is added. The retry-ladder behavior is otherwise well-specified.

---

## Plan 02-04 — CostGovernor + Pricing Table (TDD)

### Summary
Delivers cost accounting: provider-reported-or-static pricing, exactly-once 70/90 warnings, pre-call worst-case budget block via `BudgetStopResult`, plus the `BudgetInspection` data layer Phase 3 will surface. Good D-09 through D-12 coverage.

### Strengths
- `BudgetStopResult` is a value object with `raise_if_blocked()` — gives callers a choice between exception and result-pattern handling.
- Preflight is pure (no state mutation, no client call) — testable and graph-friendly.
- 11 enumerated tests cover every D-XX behavior explicitly.
- `BudgetInspection` decouples cost data from TUI concerns ahead of Phase 3.

### Concerns
- **HIGH — Silent unknown-cost handling is unsafe:** `record_usage` and `preflight` both treat unknown models as $0.00 cost (acknowledged as T-02-18). This means a model not in the pricing table can drain a budget without warning OR be preflighted past a hard stop. Real consequence: a player adds a custom OpenRouter model name, runs a long campaign, hits real costs, and CostGovernor reports $0.00 spent the whole time. At minimum, log a WARN per unknown-model call AND accumulate a separate `unknown_cost_call_count` on `CostState` so the UI can surface it.
- **MEDIUM — `state` property "returns a deep copy":** Pydantic models with mutable list fields (`warnings_sent: list[...]`) need `model_copy(deep=True)` not just `model_copy()`. The plan says "deep copy / validated model" but doesn't pin the implementation. The `test_state_property_returns_copy` test passes only if list mutation actually doesn't affect internal state — fragile.
- **MEDIUM — `apply_hard_stop()` documented but not tested:** Method exists per the plan but no test enforces it. Phase 4 will rely on it.
- **LOW — Pricing keys with embedded slashes (`openrouter/openai/gpt-4o-mini`) are exact-match strings:** Works, but a typo in the model field becomes a silent zero-cost lookup. Add a startup test verifying every model used by the fake provider config has a pricing entry.
- **LOW — Float arithmetic for cost accumulation:** Floating-point drift over a long session could cause threshold-edge flickering. `Decimal` would be more correct for money but is heavier. Accept trade-off, but consider in a later phase.

### Suggestions
- **Add `unknown_cost_call_count: int` to `CostState` and increment on every fallback to `cost_usd=0.0`.** Surface in `BudgetInspection`.
- Specify `model_copy(deep=True)` explicitly in the `state` property contract.
- Add a test for `apply_hard_stop()` semantics.
- Add a startup invariant: every model in the bundled `ProviderConfig` fakes has a pricing entry.

### Risk: **MEDIUM**
The unknown-cost silent zero is the kind of foot-gun that erodes trust in the whole governor. Worth hardening before Phase 5/6 turn on real gameplay.

---

## Plan 02-05 — OpenRouterClient + HTTP Transport

### Summary
Real OpenRouter implementation behind an injectable `HttpTransport` Protocol so the default test path stays offline. Live verification is opt-in via `SAGASMITH_RUN_LIVE_OPENROUTER=1`. Resolves the API key only inside each call.

### Strengths
- Transport injection keeps `httpx` confined to one module; everything else depends only on the Protocol.
- API key has the smallest possible lifetime — resolved per call, never crosses request/response models.
- `RedactionCanary` over `FailedEvent.message` is a nice defense-in-depth for stream errors.
- Live-call test gated by env var with explicit warning against CI use.

### Concerns
- **HIGH — Cross-plan exception contract (see Plan 02-03):** `_OpenRouterError` defines `failure_kind` to integrate with `invoke_with_retry`, but no shared base class enforces this. If `_OpenRouterError`'s shape drifts from what the ladder expects, integration silently breaks. Resolve by introducing the base class in Plan 02-03.
- **MEDIUM — SSE parsing is permissive:** Yields each `data:` line; handles `[DONE]` and JSON. Doesn't specify behavior for: comment lines (`:keep-alive`), `event: error` (some SSE producers use named events), partial JSON across chunks (rare but happens with large content + slow networks), or BOM/whitespace. Could produce malformed `LLMStreamEvent`s under real network conditions.
- **MEDIUM — `httpx.Client` lifetime in `HttpxTransport`:** Created in `__init__`, closed via `close()` / context manager. If a caller forgets to close, sockets leak. Tests should assert the production bootstrap actually uses the context-manager form.
- **LOW — Missing `HTTP-Referer` header:** OpenRouter recommends it for analytics/abuse prevention; a generic value (`"https://github.com/sagasmith/sagasmith"`) costs nothing.
- **LOW — Non-2xx body never inspected:** Plan says "NEVER response body" in error messages. Correct for security, but loses debugging info. Consider hashing the body and storing the hash in `_OpenRouterError` for support correlation without leakage.
- **LOW — Construction-time validation but not transport validation:** Constructor asserts `config.provider == "openrouter"` but doesn't validate `base_url` (could be hijacked to a malicious host via config).

### Suggestions
- **Subclass `ProviderTransportError` (proposed in Plan 02-03 review) instead of inventing `_OpenRouterError` ad-hoc.**
- Add SSE edge-case tests: comment lines, named events, mid-chunk truncation, BOM.
- Add `HTTP-Referer` and `X-Title` headers (X-Title is in the plan, Referer is not).
- Validate `base_url` against an allowlist or at least an `https://` prefix check.

### Risk: **MEDIUM**
Real network code with security-sensitive paths. The cross-plan contract gap is the highest-leverage fix.

---

## Plan 02-06 — SQLite Persistence + Turn Close

### Summary
Final wave: SQLite schema v1 (7 tables), migration runner, typed repositories per table, and the `close_turn` transactional helper that enforces PERSISTENCE_SPEC §4 ordering. Adds 5 new persisted models bringing schema export count to 25.

### Strengths
- Explicit ordered transaction with rollback semantics — directly implements the spec.
- Per-table repositories with typed inputs prevent raw-dict INSERT footguns.
- WAL journal mode for sane concurrent-read behavior.
- Schema versioning in place from day one.
- Smoke check #11 tests both happy path AND rollback — rare to see plans test the failure path explicitly.
- `RedactionCanary` sweep across all tables enforces QA-04 at storage layer.

### Concerns
- **HIGH — `conn.execute("BEGIN")` is a known-failing pattern:** STATE.md decision `[02-06]` records: *"SQLite implicit transaction semantics replace explicit BEGIN in close_turn to avoid 'cannot start a transaction within a transaction'."* This means the plan as written **was modified during execution**. Future similar plans should specify implicit transactions from the start: open conn with `isolation_level="DEFERRED"` (the default) and just call `commit()`/`rollback()`. Avoid `BEGIN` statements in code that runs alongside the Python sqlite3 module's autocommit machinery.
- **HIGH — `apply_migrations` per-file transaction with multi-statement SQL:** Plan says "Each file runs inside its own transaction." But `executescript()` issues an implicit `COMMIT` before each statement — breaking transactional guarantees. Either split the file into individual `execute()` calls inside an explicit transaction, or accept that DDL is auto-committed (SQLite cannot transactionally roll back most DDL anyway). The plan should state explicitly which path it takes.
- **MEDIUM — Rollback test uses monkeypatching, not constraint failure:** `test_close_turn_rollback_on_provider_log_failure` monkeypatches `append` to raise. This proves the Python-level rollback path but doesn't exercise the realistic failure mode (CHECK constraint violation, FK violation, UNIQUE violation). Add at least one test where SQLite itself raises mid-transaction.
- **MEDIUM — `transcript_entries` lacks `UNIQUE(turn_id, sequence)` constraint:** Phase 7 retcon will replay sequences; without a unique constraint, duplicates can sneak in. Cheap fix.
- **MEDIUM — `value_json: TEXT` for state deltas loses queryability:** Acceptable for Phase 2 audit-only use, but Phase 8 retcon will want to read these back for inverse application. Consider `JSON1`-extension functions or document the parse cost.
- **LOW — `cost_logs.warnings_fired_json: TEXT`:** Same JSON-blob pattern. Fine for now.
- **LOW — Schema export count progression (16 → 20 → 25) is fragile:** Three plans must update the same count assertion. A reverted plan or out-of-order execution breaks the suite. Consider a derived assertion: `assert len(exported) == len(LLM_BOUNDARY_AND_PERSISTED_MODELS)` instead of a magic number.

### Suggestions
- **Specify implicit-transaction usage from the start in similar future plans (no explicit `BEGIN`).** Capture the lesson in CONTEXT.md as a standing decision.
- Replace the magic-number schema export count test with a length-equality assertion against the registered-models list.
- Add `UNIQUE(turn_id, sequence)` index to `transcript_entries`.
- Add at least one rollback test driven by a real SQLite constraint violation.

### Risk: **MEDIUM**
Two of the issues are known-bad patterns the executor had to work around. The rest are hardening opportunities, not blockers.

---

## Cross-Plan Concerns

### CC-1 (HIGH) — Missing shared exception base class
Plans 02-03 and 02-05 implicitly contract on a `failure_kind` attribute for transport exceptions, but no base class enforces it. **Add `ProviderTransportError` to Plan 02-03; require Plan 02-05 (and any future provider) to subclass.**

### CC-2 (MEDIUM) — Magic-number counters in tests
Smoke check count (`5 → 7 → 8 → 10 → 11`) and schema export count (`16 → 20 → 25`) are touched by multiple plans. A reverted or reordered plan silently breaks tests. **Replace both with derived-length assertions.**

### CC-3 (MEDIUM) — Wave/file-ownership conventions only partially documented
Plan 02-02 explicitly avoids modifying `services/__init__.py` to stay parallel-safe with Plan 02-01. Plan 02-04 (Wave 3) does modify it. The convention "Wave 1 owns the package init" is implicit. **Make this explicit in CONTEXT.md.**

### CC-4 (LOW) — Pyright `pyright src` gate is enforced; full-project pyright is warnings-only
Plan 02-01 reaffirms the Phase 1 decision to keep dynamic schema-test helpers as warnings, source-code as strict. Acceptable but worth a periodic audit that nothing important is hidden in the warning stream.

---

## Overall Risk Assessment: **MEDIUM**

**Justification:** Phase 2 plans are unusually rigorous — explicit interfaces, STRIDE per plan, frontmatter contracts, enumerated tests. The trust-services foundation they deliver is the right shape and the right scope. However, three classes of issues recur:

1. **Implicit cross-plan contracts** (`failure_kind` attribute, smoke-counter integers, file-ownership conventions) that work today but will silently break under refactoring or reordering.
2. **Silent-fail tradeoffs** (unknown-model cost = $0, unknown-pricing preflight never blocks) that are documented as accepted but erode the trust the phase is supposed to establish.
3. **Known-buggy patterns the executor adapted around** (`BEGIN` in `close_turn`, multi-statement DDL "per-file transaction") that should be fixed in the source plans so similar future plans don't repeat them.

None of these block the phase from delivering value — and the executor evidently navigated all of them, since STATE.md marks Phase 2 complete. But they're the kinds of issues that compound across phases. Worth folding the lessons into CONTEXT.md before Phase 3 planning starts.

### Recommended top-3 follow-ups (if revisiting)
1. Add `ProviderTransportError` base class and refactor `_OpenRouterError` to subclass it.
2. Add `unknown_cost_call_count` to `CostState` and surface in `BudgetInspection`; stop pretending unknown models are free.
3. Replace magic-number test counters with derived-length assertions.

---

## Codex Review

Codex CLI was detected, but the review could not be completed in this environment. Attempts with the default configured model and fallback model names failed before producing reviewer feedback.

```text
Codex review failed or returned empty output. ExitCode=1

OpenAI Codex v0.122.0 (research preview)
workdir: C:\PersonalDevFiles\KiloCodeFiles\AI-TTRPG-GoAnywhereDoAnything
provider: openai
approval: never
sandbox: workspace-write

ERROR: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-5.5' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again."}}
ERROR: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-5' model is not supported when using Codex with a ChatGPT account."}}
ERROR: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-4.1' model is not supported when using Codex with a ChatGPT account."}}
```

No Codex consensus signals were used beyond the invocation failure itself.

---

## OpenCode Review

# Phase 2 Plan Review

## Summary

The Phase 2 plans deliver a comprehensive deterministic trust services layer for SagaSmith. The plans are well-organized into 4 waves with clear dependencies, each building on earlier work without scope creep. The architecture properly separates concerns: secrets/encryption handling (02-01), deterministic dice/rules math (02-02), provider abstraction + fake client (02-03), cost governance (02-04), real OpenRouter wiring (02-05), and SQLite persistence (02-06). Together they address all Phase 2 requirements while maintaining the "no paid calls by default" invariant.

---

## Plan-by-Plan Assessment

### 02-01-PLAN.md — Typed trust-service errors, SecretRef resolver, redaction expansion

**Strengths:**
- Clean exception hierarchy inheriting from `TrustServiceError`, following the existing `PersistedStateError` pattern
- `SecretRef` with model validator enforcing keyring requires account, env requires none
- Proper secret resolution without logging; `scrub_for_log` helper is reusable
- HP invariant added to both `CharacterSheet` and `CombatantState` with clear error messages
- Fixture override validation now re-validates under strict Pydantic rules (fixes D-16 gap)
- Test coverage includes env var missing/set, keyring missing/set, redaction labeling

**Concerns:**
- **LOW**: No explicit test for empty-string env var (`SAGASMITH_TEST_KEY=""`). Current behavior would raise "not set" but semantically it's set to empty. Consider documenting expected behavior.
- **LOW**: `TrustServiceError.__str__` is not explicitly tested for avoiding secret leakage — the subclass tests cover it, but a dedicated test adds defense-in-depth.

**Suggestions:**
- Add `pytest.mark.smoke` test for: `resolve_secret(env, "EMPTY_VAR", ...)` where `os.environ["EMPTY_VAR"] = ""` and verify it raises `SecretRefError`.

---

### 02-02-PLAN.md — DiceService with seeded deterministic replay and PF2e degree math

**Strengths:**
- Excellent test coverage: 14 explicit degree boundary cases + nat1/nat20 adjustment cases
- SHA-256 deterministic derivation (no RNG internals to serialize) per D-14
- Injected clock for deterministic timestamps in tests
- Clean separation: `compute_degree` is pure function, `DiceService` is the roll engine
- All RollResult fields populated correctly

**Concerns:**
- **LOW**: SHA-256 modulo distribution is theoretically predictable. For PF2e this is acceptable (replay matters more than randomness), but worth documenting.
- **LOW**: No test for cross-purpose replays (same roll_index, different purpose). Intentionally allowed per D-14 ("purpose" is part of the key), but a quick test confirming naturals differ would add confidence.

**Suggestions:**
- Add a quick test: roll_index=0 for purpose="a" vs purpose="b" should yield different naturals.

---

### 02-03-PLAN.md — LLMClient protocol, retry ladder, deterministic fake client

**Strengths:**
- Clean Protocol abstraction covering both `complete` and `stream`
- Retry ladder exactly per D-03: repair attempt → cheap-model fall-back → exhaust
- Metadata-only provider logs with `RedactionCanary` gating on `safe_snippet`
- `ProviderConfig` enforces fake requires no key, openrouter requires key
- Smoke check #8 proves fake round-trip

**Concerns:**
- **MEDIUM**: The retry ladder calls `request.model_copy(update={"model": cheap_model})` on attempt 3 but `model` is part of the request signature. Need to verify this copies correctly — Pydantic's `model_copy` should handle it.
- **LOW**: `jsonschema` library added as main dependency. This is necessary for structured validation, but worth confirming it doesn't balloon dependencies.
- **LOW**: No timeout in retry ladder. D-03 mentions rate_limit with provider delay but this is handled by transport (Plan 02-05). Consider documenting that `timeout_seconds` flows from request to transport.

**Suggestions:**
- Add a smoke test verifying: `request.model_copy(update={"model": "different"})` actually changes the model field.

---

### 02-04-PLAN.md — CostGovernor with static pricing, budget warnings, preflight

**Strengths:**
- 70%/90% warnings fire exactly once per D-11
- Preflight is pure (no state mutation) per D-12 - caller decides whether to block
- `BudgetInspection` ready for Phase 3 TUI `/budget` command
- Unknown model gracefully returns 0.0 approximate cost (not block) - good dev UX
- Smoke checks #9 and #10 prove warning-once and preflight-blocked behaviors

**Concerns:**
- **MEDIUM**: `preflight` returns `blocked=True` but doesn't mutate internal state. The caller must call `governor.apply_hard_stop()` after a blocked call to persist the hard_stopped flag. The pattern is documented but worth testing end-to-end in Phase 4 when graph integrates it.
- **LOW**: D-10 formula uses `max_tokens_fallback` which is a parameter, not requested `max_tokens`. This is correct per D-10 ("worst-case based on prompt + configured max_tokens"), but ensure the Phase 3 TUI wires this correctly.

**Suggestions:**
- Add integration test (Phase 4 scope): after preflight blocks, verify `apply_hard_stop()` sets state.hard_stopped=True.

---

### 02-05-PLAN.md — OpenRouterClient with injected HTTP transport

**Strengths:**
- Clean `HttpTransport` Protocol isolating httpx from client code
- No httpx import in openrouter.py — testable with fake transport
- API key resolved only during method call, never stored
- SSE streaming with delta accumulation and usage update yielding
- Live test opt-in only per D-01

**Concerns:**
- **LOW**: Base URL hardcoded but injectable via parameter. Good.
- **LOW**: `X-Title: SagaSmith` header could be configurable. Minor.
- **LOW**: Error message on non-200 status does not include response body, but in some OpenRouter error envelopes the body contains a useful message. Consider logging at DEBUG level without persisting.

**Suggestions:**
- Add DEBUG-level logging for error response bodies (not persisted).

---

### 02-06-PLAN.md — SQLite trust-records, repositories, turn-close transaction

**Strengths:**
- 7 comprehensive tables covering all Phase 2 persistence scope
- `close_turn` enforces explicit transaction with rollback-on-failure
- PERS-04 explicit test: after failed close, zero turn_record rows
- `RedactionCanary` extends to all persisted tables
- Schema count increases correctly (20 → 25)

**Concerns:**
- **MEDIUM**: TurnCloseBundle overwrites turn_record status to "complete" on commit. If caller passes `status="needs_vault_repair"` it gets silently overwritten. This is likely intentional but worth documenting.
- **LOW**: Foreign key constraints defined but on some tables (`turn_id` references not enforced in DB). Acceptable since Phase 2 doesn't have turns yet.
- **LOW**: Transcript could grow unbounded - noted as Phase 7 (memory/vault) scope. Appropriate deferral.

**Suggestions:**
- Document that TurnCloseBundle always overwrites status, or add validation.

---

## Cross-Plan Issues

### Interface Compatibility — GOOD
Each plan correctly consumes and produces types from/to earlier plans:
- Plan 02-01 exports `TrustServiceError`, `SecretRef`, `resolve_secret`
- Plan 02-02 produces `RollResult` (already in schemas)
- Plan 02-03 imports `LLMClient`, produces `ProviderConfig`, `ProviderLogRecord`
- Plan 02-04 imports `TokenUsage`, `CostState`, exports `BudgetStopError` (from 02-01)
- Plan 02-05 imports `HttpTransport`, produces `LLMClient`
- Plan 02-06 imports provider logs, roll logs, cost logs

### Secret Handling — GOOD
- `resolve_secret` raises without leaking value ✓
- Provider logs metadata-only with RedactionCanary gating ✓
- API key in headers only, never in request/response models ✓

### Performance — GOOD
- SQLite WAL mode ✓
- Transactional close_turn batches inserts ✓
- Streaming SSE yields without full-buffer ✓

---

## Risk Assessment

**Overall Risk Level: LOW**

The Phase 2 plans deliver the deterministic trust services layer with:
- Clear separation from later phase concerns (TUI, graph, vault)
- Strong security model (redaction canary, typed errors, no secret leaks)
- Comprehensive test coverage including smoke checks
- Proper dependencies and wave organization

No HIGH-severity issues identified. The MEDIUM concerns are around integration patterns (preflight→apply_hard_stop, turn_close status overwrite) and are design decisions that could be clarified rather than bugs.

---

## Suggestions Summary

1. **Add empty-string env var test** (Plan 02-01): Document expected behavior when env var set to `""`.
2. **Add cross-purpose roll test** (Plan 02-02): Verify different purposes yield different naturals.
3. **Verify model_copy works** (Plan 02-03): Smoke test for retry ladder model swap.
4. **Document apply_hard_stop pattern** (Plan 02-04): Integration pattern for Phase 4.
5. **Add DEBUG error logging** (Plan 02-05): Non-persisted error body logging.
6. **Document status overwrite** (Plan 02-06): TurnCloseBundle always overwrites to "complete".

---

## Consensus Summary

Three AI systems successfully reviewed the Phase 2 plans (Gemini, the agent, OpenCode). All three found the overall planning structure strong, with clear phase boundaries, no-paid-call defaults, good dependency ordering, and unusually comprehensive tests and threat modeling. The strongest shared risk area is Plan 02-06 transaction semantics: Gemini and the agent both flagged the explicit `conn.execute("BEGIN")` instruction as inconsistent with SQLite/Python transaction behavior and with the later recorded STATE.md decision. Provider streaming/SSE robustness was also raised by Gemini and the agent. Secret handling and deterministic dice were broadly praised across all reviewers.

### Agreed Strengths

- **Strong scope control and phase fit**: All reviewers agreed the six plans correctly stop at deterministic trust services and defer TUI, graph runtime, full PF2e gameplay, and vault work to later phases.
- **No-paid-call architecture**: Gemini, the agent, and OpenCode praised deterministic fakes, injected transports, opt-in live OpenRouter verification, and offline smoke tests.
- **Secret-safety design**: Reviewers consistently highlighted typed secret references, safe exception text, metadata-only provider logs, and `RedactionCanary` integration as strong trust foundations.
- **Deterministic rules primitives**: All reviewers viewed Plan 02-02 as very low risk due pure functions, SHA-256 replay derivation, injected clocks, and exhaustive degree-of-success tests.
- **Test-first verification**: TDD sections, stable smoke checks, schema exports, rollback tests, and STRIDE/threat registers were repeatedly cited as high-quality planning practices.

### Agreed Concerns

1. **SQLite transaction contradiction / `BEGIN` risk (HIGH)**
   - Gemini and the agent both flagged `conn.execute("BEGIN")` in Plan 02-06 as conflicting with Python sqlite3 implicit transactions and the STATE.md decision to avoid explicit `BEGIN` after hitting `cannot start a transaction within a transaction`.
   - Recommended action: update Plan 02-06 to specify implicit sqlite3 transactions (`commit`/`rollback`) rather than explicit `BEGIN`, and document the lesson as a standing persistence planning rule.

2. **SSE / streaming failure robustness (MEDIUM)**
   - Gemini highlighted malformed JSON chunks causing generator crashes.
   - The agent highlighted comment lines, named error events, BOM/whitespace, chunk truncation, and transport-level stream edge cases.
   - Recommended action: add explicit SSE edge-case tests and define streaming retry/failure ownership (Phase 2 service vs Phase 4/6 graph logic).

3. **Cross-plan provider exception contract (HIGH/MEDIUM)**
   - The agent identified an implicit `.failure_kind` contract between `invoke_with_retry` and `_OpenRouterError` with no shared base class.
   - Gemini's streaming-retry ambiguity points to the same broader provider-error boundary needing stronger definition.
   - Recommended action: define a shared `ProviderTransportError`/typed transport failure interface in the provider abstraction and require OpenRouter and future providers to use it.

4. **Cost unknown-model behavior (MEDIUM/HIGH)**
   - The agent considered treating unknown model costs as `$0.00` unsafe for trust, even if documented.
   - Gemini and OpenCode accepted it more as development-friendly, but still noted static pricing freshness and integration concerns.
   - Recommended action: at least track/report unknown-cost calls, and consider surfacing unknown pricing in `BudgetInspection` so the UI cannot imply the budget is fully trustworthy when pricing is missing.

5. **Fragile count-based assertions (MEDIUM/LOW)**
   - The agent flagged schema/smoke magic numbers (`16 → 20 → 25`, `5 → 7 → 8 → 10 → 11`) as cross-plan fragility.
   - Recommended action: use derived assertions against registered model/check lists where practical.

### Divergent Views

- **Overall risk level**: Gemini and OpenCode rated the plans LOW risk; the agent rated them MEDIUM due cross-plan contracts, silent-fail cost behavior, and known SQLite pitfalls. The practical consensus is LOW implementation risk for isolated plans, MEDIUM integration/maintenance risk unless follow-ups are folded into planning.
- **Unknown model costs**: OpenCode viewed `$0.00 approximate` as good development UX; the agent viewed it as a trust-eroding foot-gun. Treat this as a product decision: acceptable only if clearly surfaced to users and logs.
- **OpenRouter error body handling**: OpenCode suggested DEBUG-level non-persisted logging for useful response bodies; the agent emphasized avoiding response-body leakage and suggested hashing instead. Security posture should favor hashing/redacted diagnostics over raw body logging.
- **Plan 02-06 status overwrite**: OpenCode flagged TurnCloseBundle overwriting `needs_vault_repair` to `complete`; the other reviewers did not mention it. This likely needs documentation rather than a design change, because Phase 7 owns vault repair state.

### Top Feedback to Feed Back into `/gsd-plan-phase --reviews`

1. Fix Plan 02-06 transaction instructions: remove explicit `BEGIN`, clarify migration transaction limitations, and add a SQLite-constraint-driven rollback test.
2. Strengthen provider failure contracts: add a shared typed transport exception/failure interface and clarify complete-vs-stream retry ownership.
3. Surface unknown-cost uncertainty instead of silently treating unknown models as free; consider `unknown_cost_call_count` or equivalent inspection field.
4. Add SSE edge-case tests for malformed chunks, comments, named error events, and redacted stream failures.
5. Replace fragile magic-number smoke/schema assertions with derived assertions where possible.
