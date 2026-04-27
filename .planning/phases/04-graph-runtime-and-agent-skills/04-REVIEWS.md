---
phase: 4
reviewers: [gemini, claude, codex, opencode]
reviewed_at: 2026-04-27T18:14:07Z
plans_reviewed: [04-01-PLAN.md, 04-02-PLAN.md, 04-03-PLAN.md]
skipped_reviewers:
  coderabbit: missing
  qwen: missing
  cursor: missing
notes:
  - Gemini initially required trusted workspace configuration; retried with GEMINI_CLI_TRUST_WORKSPACE=true.
  - Codex default model failed due CLI version/model mismatch; retried with a compatible model override.
---

# Cross-AI Plan Review — Phase 4

Phase 4 was reviewed by four external AI systems available on this machine: Gemini, the agent CLI, Codex, and OpenCode. CodeRabbit, Qwen Code, and Cursor were not installed. The executing runtime is Kilo, so no available reviewer was skipped as the self CLI.

---

## Gemini Review

This review evaluates implementation plans **04-01**, **04-02**, and **04-03** for Phase 4 of the SagaSmith project. These plans establish the LangGraph orchestration runtime, persistent checkpointing/interrupt systems, and the Agent Skills adapter layer.

### 1. Summary

The Phase 4 plans provide a robust and highly disciplined transition from isolated services to a coordinated agent graph. By leveraging LangGraph’s native checkpointing and interrupt primitives while maintaining a strict "thin-node" architecture (where agents are pure functions and services are injected), the design ensures the system remains testable, deterministic, and crash-safe. The decision to use a TypedDict mirror of the Pydantic `SagaState` with import-time drift guards is an excellent optimization that balances LangGraph’s performance needs with the project’s strict schema validation requirements.

### 2. Strengths

- **Infrastructure-as-Code Safety**: The use of import-time drift guards (`set(TypedDict.keys) == set(Pydantic.fields)`) in Plan 04-01 is a top-tier defensive programming pattern that prevents silent regressions as the core schema evolves.
- **Graceful Degradation**: Plan 04-02 ensures that TUI commands (like `/pause`) fall back gracefully if the graph is not bound, maintaining backward compatibility with Phase 3 unit tests.
- **Deterministic Integrity**: The integration of `close_turn` within the Archivist node (via injected callables) correctly implements the complex transaction ordering required by `PERSISTENCE_SPEC.md`, ensuring that turn status, transcripts, and checkpoints are committed atomically.
- **Context Efficiency**: The Agent Skills adapter (Plan 04-03) follows a "metadata-first" approach, where agents only see compact catalogs by default, fulfilling the goal of progressive disclosure and context budget preservation.
- **Security Posture**: RedactionCanary is applied consistently across all new persistence boundaries: the agent activation log, skill body scanning, and interrupt payloads.

### 3. Concerns

- **LOW — ContextVar in async context**: Plan 04-03 uses `contextvars` to pass the `AgentActivationLogger` to nodes. While safe in the current single-threaded Textual/LangGraph setup, if the graph ever adopts parallel node execution, the implementation must ensure that `SagaGraphState` updates do not collide.
- **LOW — YAML-lite brittleness**: The hand-rolled frontmatter parser in Plan 04-03 avoids a heavy PyYAML dependency, consistent with the project's local-first/minimal-dependency ethos. However, it may fail on valid YAML edge cases such as folded blocks or complex lists if future `SKILL.md` files become more complex.
- **MEDIUM — SqliteSaver table names**: LangGraph's `SqliteSaver` creates its own tables (`checkpoints`, `writes`). While Plan 04-02 includes a check for collisions, there is a risk that a future LangGraph update could introduce a table name that conflicts with SagaSmith's internal repositories.
- **LOW — Interrupt payload volume**: The `pending_interrupt` field is added to state. If large payloads are ever passed through interrupts, they will be serialized into every subsequent checkpoint until cleared, potentially bloating the database.

### 4. Suggestions

- **Schema versioning for skills**: Add a `schema_version` or `min_app_version` field to `SKILL.md` frontmatter. This allows `SkillStore` to skip skills that are incompatible with the current runtime logic during scan.
- **Explicit SqliteSaver namespace**: Consider prefixing LangGraph-managed tables if the library allows, or explicitly document the reserved table names in persistence docs to prevent future developers from choosing names like `writes` or `checkpoints` for new repositories.
- **Node execution timeout**: Since nodes are pure functions injected with an `LLMClient`, consider adding a timeout wrapper at the `build_saga_graph` level to ensure a hanging provider call does not block the TUI indefinitely without an interrupt opportunity.

### 5. Risk Assessment: LOW

The overall risk is **Low**. The plans are exceptionally detailed, cite specific sections of specifications (`GAME_SPEC`, `ADR-0001`, `PERSISTENCE_SPEC`), and provide clear TDD behavior tests for every new component. The phased rollout (Foundation → Persistence/Interrupts → Skills) follows a logical dependency chain that minimizes rework. The inclusion of a no-paid-call smoke suite and the preservation of existing 295+ tests maintain the project's quality bar throughout this major architectural shift.

---

## the agent Review

# Phase 4 Plan Review: Graph Runtime and Agent Skills

## Overall Summary

These three plans (04-01, 04-02, 04-03) deliver Phase 4's GRAPH-01 through GRAPH-05, AI-12, and SKILL-01 through SKILL-05 in a coherent wave structure: skeleton graph → persistent checkpoints + interrupts → skills adapter. The plans are notably well-grounded in the existing codebase, referencing real Phase 3 patterns like StrEnum, lazy canary factories, and the single-thread SQLite connection, and trace cleanly to ADR-0001's architectural commitments. They are detailed, threat-modeled, and TDD-driven, but they are also large and ambitious for two-task plans, with several embedded scope expansions and a few correctness risks that should be addressed before execution.

---

## Plan 04-01: LangGraph Runtime Foundation

### Strengths

- TypedDict mirror of `SagaState` with import-time field-drift assertion is exactly the right shape for LangGraph integration without paying Pydantic cost on every node transition.
- `PHASE_TO_ENTRY` exhaustiveness guard at import time catches schema evolution bugs at module load, not at runtime.
- Pure-function node contract (test 5 deepcopy comparison) is a strong invariant that pays dividends in Plans 04-02 and 04-03.
- Seeded-replay test for `rules_lawyer_node` validates determinism early.
- Thin-node rule (no SQL/LLM/IO inside nodes) is enforced by tests, not just convention.

### Concerns

- **MEDIUM — Schema modification mid-plan:** Task 2 adds `pending_narration: list[str]` to both `SagaGraphState` and `SagaState`. This is a cross-cutting schema change buried in a task focused on agent nodes; it touches JSON Schema export, evals/fixtures, and any existing SagaState builders. The plan acknowledges this in verification step 6 but does not budget for the test/fixture sweep. Recommend hoisting this to Task 1 with an explicit fixture-update subtask.
- **MEDIUM — Onboarding routing collapse:** Routing both `onboarding` and `character_creation` to one `onboarding` node, and both `play` and `combat` to `oracle`, conflates phases that have different state requirements. The `combat` phase requires `CombatState`; routing it to oracle without a sub-route may invite Phase 5 rework. The plan acknowledges this as deferred, but the routing table will need rewriting, not just extension.
- **LOW — `langgraph>=1.1,<2` pin:** Confirm the version range is actually published and resolves cleanly before planning around it.
- **LOW — `pending_narration` semantic ambiguity:** Is the list cumulative across turns or reset per turn? Orator returns a fresh list; archivist clears `pending_player_input` but not `pending_narration`. Specify ownership and lifecycle.
- **LOW — `PHASE_TO_ENTRY` type mismatch:** `END` is a sentinel, not a string. `PHASE_TO_ENTRY: dict[str, str]` is wrong if it contains `END`.

### Suggestions

- Move `pending_narration` schema addition to Task 1 with explicit fixture updates.
- Add a routing test for `phase="combat"` with non-null `combat_state` to make the deferred Phase 5 commitment explicit.
- Type `PHASE_TO_ENTRY` as a union that includes the END sentinel, or split terminal routes from node-entry routes.
- Pin LangGraph only after verifying the exact range resolves with `uv`.

### Risk: LOW–MEDIUM

Skeleton-only delivery with strong tests. Main risk is the embedded schema change.

---

## Plan 04-02: Persistent Graph + Interrupts + Activation Log

### Strengths

- Migration 0005 with FK to `turn_records(turn_id)` correctly enforces the no-orphan-log-row invariant.
- Activation logger as node wrapper, not node-internal instrumentation, preserves separation of concerns.
- Mapping LangGraph `Interrupt` exceptions to `outcome="interrupted"` rather than `error` preserves the AI-12 audit distinction.
- Pre-narration checkpoint via `interrupt_before=["orator"]` aligns with `PERSISTENCE_SPEC §5`.
- Threat T-04-07 (SqliteSaver table-name collision) is appropriate paranoia for sharing a connection.
- Preserving Phase 3 `/pause` and `/line` SafetyEvent writes while adding interrupt dispatch is the correct backward-compatible move.

### Concerns

- **HIGH — `pending_interrupt` as state field may bypass LangGraph's native interrupt model:** LangGraph 1.x has first-class `interrupt()` / `Command(resume=...)` primitives. Using `update_state({"pending_interrupt": ...})` to short-circuit edges is a shadow mechanism that may not trigger LangGraph's own interrupt machinery, may not compose cleanly with `interrupt_before=["orator"]`, and may confuse future Phase 6+ developers who reach for the documented resume API. Recommend using LangGraph's native interrupt primitives or documenting why the state-field approach is intentional.
- **HIGH — Two-task plan is dramatically under-scoped:** Task 2 touches checkpoints, interrupts, all five agent nodes, four TUI files, runtime wiring, and three test files with eleven behaviors. This is likely a 600–1000 LOC implementation hidden as one task. Split into checkpoints/persistent graph, interrupts/TUI wiring, and activation-log wrapper integration.
- **MEDIUM — `record_pre_narration_checkpoint` ownership unclear:** The plan says the TUI runtime or the archivist's turn closer calls it, but those are very different call sites. Specify a single owner.
- **MEDIUM — Budget hard-stop wrapping leaks interrupt concepts into nodes:** The wrapper should catch `BudgetStopError` and convert it to an interrupt rather than teaching pure nodes about interrupt envelope shape.
- **MEDIUM — `precheck_estimated(0.0)` is dead code:** A zero estimate will always pass. Defer the wiring until Phase 6 has real estimates or inject a meaningful estimator.
- **MEDIUM — Migration and retcon semantics:** `agent_skill_log` lacks ON DELETE cascade; that may be desirable for audit but should be documented for Phase 8 retcon handling.
- **LOW — RetconCommand interrupt without confirmation:** Even as a stub, posting `InterruptKind.RETCON` may halt a turn before Phase 8 implements the resume/confirmation flow.
- **LOW — Single connection and async execution:** Confirm Phase 4 graph nodes are sync-only so SqliteSaver and Textual do not write concurrently through the same connection.

### Suggestions

- Re-examine the interrupt mechanism against current LangGraph docs and prefer `interrupt()` + `Command(resume=...)` unless the state-field pattern is intentional and documented.
- Split Task 2 into at least three smaller tasks for atomic commits and reviewability.
- Move `BudgetStopError` → interrupt translation into the graph wrapper.
- Defer `precheck_estimated` calls until real estimates exist.
- Gate RetconCommand graph effects behind confirmation or keep it acknowledge-only until Phase 8.
- Add an explicit table-name-collision test for all known SqliteSaver tables (`checkpoints`, `writes`, `checkpoint_blobs`, `checkpoint_migrations`) against SagaSmith migrations.

### Risk: HIGH

Two architectural concerns (non-idiomatic interrupt mechanism and undersized task split) plus multiple coupling issues make this plan the highest-risk piece. It needs revision before execution.

---

## Plan 04-03: Skills Adapter + First-Slice Catalog

### Strengths

- Hand-rolled frontmatter parser is consistent with the project's minimalism.
- Collecting scan errors instead of raising on the first bad `SKILL.md` makes discovery robust.
- RedactionCanary applied to skill bodies at scan time is good defense-in-depth.
- ContextVar handoff for activation logging is a clean way to let nodes call `set_skill` without re-plumbing services.
- 256KB body cap prevents future memory foot-guns.
- Production count assertion (14 skills, 0 errors) is a strong CI gate.

### Concerns

- **HIGH — Two-task scope is under-budgeted:** Task 2 ships 14 `SKILL.md` files, modifies bootstrap, modifies all five agent nodes, adds a contextvar mechanism, adds `first_slice_only` filtering, and retests Plan 04-02's full play-turn scenario. This should be multiple tasks.
- **HIGH — `first_slice_only=True` introduced mid-plan:** Task 1's SkillStore design does not define `first_slice_only` or a `first_slice` field, but Task 2 relies on them. Add both to Task 1.
- **MEDIUM — `load_skill` for deterministic skills is mostly audit plumbing:** RulesLawyer loads the markdown body but ignores it and calls Python handlers. That is fine as a logging/auditing hook, but SKILL-03 is proven by the loader API and tests, not by this stub usage.
- **MEDIUM — Frontmatter parser fragility:** Single-line-only fields are acceptable now but should be documented clearly or expanded to support simple folded text.
- **MEDIUM — Silent downgrade of `allowed_agents: ["*"]` in agent-scoped skills:** Silent rewrite is worse than rejection. Reject or warn loudly.
- **MEDIUM — Onboarding skill rarely activates:** Since Phase 3 already ran onboarding, Phase 4's onboarding node is mostly pass-through. Either document why the skill is shipped now or drop it until it matters.
- **LOW — Archivist `memory-packet-assembly` placeholder is misleading:** If the node does not actually assemble memory packets, leave the skill name unset or use an honest stub indicator.
- **LOW — Deferred skill coverage should be explicit:** Specs list many more skills than the 14 shipped. List non-first-slice deferrals in the summary to prevent drift.

### Suggestions

- Split Task 2 into bootstrap/contextvar integration, SKILL.md catalog shipping, and deterministic handler wiring.
- Add `first_slice: bool` to `SkillRecord` and `first_slice_only: bool` to SkillStore in Task 1.
- Reject, rather than silently downgrade, agent-scoped skills that declare `allowed_agents: ["*"]`.
- In 04-03 SUMMARY, list every non-shipped spec skill with target phase.
- Clarify whether deterministic `SKILL.md` files are metadata-only until LLM agents consume them.
- Clarify relationship between `services-capabilities.md` entries and SKILL.md files.

### Risk: MEDIUM–HIGH

The adapter design is sound. The task split is too coarse and several details need tightening.

---

## Cross-Cutting Observations

### Strengths Across All Three Plans

- Excellent grounding in existing codebase patterns.
- Threat models per plan with traceable mitigations.
- Strong test coverage with behavior-numbered TDD and deterministic fixtures.
- Clear deferral notes for Phases 5–8.

### Concerns Across All Three Plans

- **HIGH — Plan size:** All three plans use a two-task structure that buries 5–15 behaviors per task. Prior phases had tighter plan scopes; Phase 4 should be split into smaller tasks or subplans.
- **MEDIUM — Schema evolution coordination:** Plans 04-01 (`pending_narration`) and 04-02 (`pending_interrupt`) both modify `SagaState` and `SagaGraphState`. The JSON Schema export and external contracts will change; verify and document this.
- **MEDIUM — TUI does not yet invoke graph per turn:** Plans show graph construction and command interrupt posting but not the per-turn invocation path from TUI input. Consider adding a minimal end-to-end TUI input → graph turn → stub narration smoke test.

### Risk Assessment Summary

| Plan | Risk | Primary Drivers |
|------|------|-----------------|
| 04-01 | LOW–MEDIUM | Skeleton only; embedded schema change |
| 04-02 | HIGH | Interrupt mechanism uncertainty; oversized task; node/interrupt coupling |
| 04-03 | MEDIUM–HIGH | Oversized task; `first_slice_only` introduced late; deterministic-skill semantics |

**Overall Phase 4 risk: MEDIUM–HIGH.** Plan 04-02 needs architectural review of interrupt mechanics against current LangGraph idioms, and all three plans benefit from finer task splitting. Add an end-to-end “graph runs one turn from TUI input” smoke test before declaring Phase 4 complete.

---

## Codex Review

## 04-01-PLAN.md

### 1) Summary

Strong “thin-skeleton first” plan with good contract tests, explicit routing, and clear separation between agent stubs and deterministic services. Biggest risk is schema churn (`pending_narration`) and a few API/contract assumptions (LangGraph and existing schema shapes) that could cascade into many fixture updates.

### 2) Strengths

- Clear scope boundary: GRAPH-01 only; checkpoints/interrupts/skills deferred cleanly to 04-02/04-03.
- Good drift prevention: exhaustive phase routing guard and SagaState↔TypedDict key-set guard.
- Healthy architectural discipline: nodes are pure, no SQL/LLM/vault I/O.
- TDD behaviors are concrete and verify import-weight (no accidental `textual`/`sqlite3` pulls).
- Bootstrap/service injection design supports deterministic testing (`llm=None`).

### 3) Concerns

- **HIGH — `pending_narration` blast radius:** Adding `pending_narration` in 04-01 affects schemas, JSON Schema export counts, fixtures, persistence, and evals for a skeleton plan. Consider postponing to 04-02 where checkpoints/turn-close actually need it.
- **HIGH — Seeded replay test over-asserts roll ID stability:** Many RNG designs keep outcomes deterministic while generating unique IDs. Test `natural`/`total` and possibly a deterministic roll key rather than `roll_id`.
- **MEDIUM — `TypedDict(total=True)` vs minimal dict fixtures:** Full TypedDict plus “minimal dict literal” can fight each other. Either embrace full-state fixtures or use `NotRequired` where fields are optional at runtime.
- **MEDIUM — SceneBrief stub may be brittle:** If `SceneBrief` has rich required schema, use the smallest valid constructor or an existing fixture factory.
- **LOW — Combat routing is currently same as play:** Acceptable now, but explicitly call out combat sub-routing deferral.

### 4) Suggestions

- Move `pending_narration` to 04-02, or gate it to avoid early schema churn.
- Update dice determinism tests to assert same inputs → same roll outcome rather than same ID.
- Decide one canonical graph-state fixture builder early, e.g. `make_graph_state()` in tests.
- Confirm LangGraph API assumptions with a tiny spike before adding broad behavioral tests.

### 5) Risk Assessment

**MEDIUM** — The plan is well-structured, but early schema expansion and shaky assumptions could create broad fixture repair work.

---

## 04-02-PLAN.md

### 1) Summary

Ambitious and mostly aligned with Phase 4 success criteria: persistence checkpoints, interrupts, and activation logging. The main risks are LangGraph checkpoint semantics versus the plan’s turn/thread model, reliable checkpoint ID access, and preserving thin nodes while also needing turn lifecycle database writes.

### 2) Strengths

- Good auditability: activation log schema plus `success/interrupted/error` outcomes are a solid spine for later evals.
- Security discipline: RedactionCanary on persisted log payloads and planned interrupt payloads.
- Thoughtful rollback semantics: logger participates in the caller’s transaction, so rollback removes log rows.
- Clear interrupt taxonomy (`pause/line/retcon/budget_stop/session_end`) matches product needs.
- Explicit non-collision testing for SqliteSaver table names is pragmatic and CI-friendly.

### 3) Concerns

- **HIGH — Thread identity mismatch:** Tests use `thread_id = turn_id`, while runtime suggests `thread_id = campaign:<id>`. This impacts resume semantics, checkpoint lookup, and how “final checkpoint means resume at next prompt” works.
- **HIGH — Checkpoint ID access may be assumed incorrectly:** Pre-narration checkpoint ref recording depends on extracting a `checkpoint_id` from LangGraph state; this may not be directly accessible as implied. If not, significant redesign may be needed.
- **HIGH — Potential thin-node-rule conflict:** The plan hints that Oracle opens the turn record before RulesLawyer to satisfy FK constraints. That would be database I/O in a node unless moved to a wrapper/service boundary.
- **MEDIUM — `interrupt_before=["orator"]` resume semantics need proof:** Ensure RulesLawyer never reruns when narration resumes, otherwise deterministic rule outcomes could duplicate.
- **MEDIUM — `pending_interrupt` expands canonical state:** Interrupts may be better as LangGraph interrupts or out-of-band events than core game state.
- **LOW — Budget precheck stub belongs in a wrapper:** A zero-estimate precheck inside nodes is a leaky abstraction.

### 4) Suggestions

- Choose and document one checkpoint threading model:
  - **Option A (recommended):** `thread_id = campaign_id`; treat checkpoints as campaign-thread history and keep `turn_id` in state + checkpoint_refs.
  - **Option B:** `thread_id = turn_id`; runtime must maintain and advance current turn thread IDs deterministically.
- Do not rely on checkpoint ID extraction until confirmed by a spike; if unavailable, store a deterministic SagaSmith checkpoint key and treat LangGraph’s internal ID as opaque.
- Keep database writes out of nodes; implement turn open/close/checkpoint-ref recording as wrapper services around graph invocation boundaries or node wrappers.
- Prefer real LangGraph interrupt primitives over `pending_interrupt` in state unless persisted interrupts in `SagaState` are intentional.
- Add a test proving rules results remain stable on narration retry: same `check_results`, no new dice rolls.

### 5) Risk Assessment

**HIGH** — The plan has many moving parts and unresolved foundational uncertainties around checkpoint IDs, thread identity, and DB write placement.

---

## 04-03-PLAN.md

### 1) Summary

Good adapter-first approach that matches ADR-0001 and keeps dependencies minimal. Main risks are packaging/resource distribution, brittle exact skill-count assertions, and synthetic secret fixtures potentially tripping secret scanning.

### 2) Strengths

- Clean separation: store/catalog/loader/errors is a maintainable surface for later orchestration changes.
- Strong validation posture: kebab-case name regex, size limits, duplicate handling, authorization, canary scanning.
- Lightweight import goal is explicitly tested.
- Contextvar handoff for activation logging is practical and keeps nodes decoupled from wrappers.
- `first_slice_only` gating aligns well with SKILL-05 and trust-before-breadth.

### 3) Concerns

- **HIGH — Distribution risk:** Plans do not explicitly ensure `SKILL.md` files are included in the built package (wheel/sdist). Installs may run with an empty store without package-data configuration.
- **HIGH — Secret-scanner risk:** A fixture string matching secret patterns may trigger gitleaks/pre-commit and break CI even if tests pass.
- **MEDIUM — YAML-lite parser limitations:** The parser rejects common YAML features. This is acceptable if intentional, but needs a supported-subset contract.
- **MEDIUM — Exact `== 14` skill-count assertions are brittle:** Adding a skill later breaks tests even if required behavior remains correct.
- **LOW — `src/sagasmith/skills/__init__.py` as resource package:** Fine, but make clear to contributors that this is resources, not importable code.

### 4) Suggestions

- Add packaging config to include `SKILL.md` as package data and add a test that loads skills from an installed-style path, not just repo-relative paths.
- Use an existing canary test token or safe sentinel to avoid gitleaks collisions.
- Replace exact-count tests with required-set containment plus `no errors`.
- Document the supported frontmatter subset.
- Make `SkillStore.scan()` deterministic across filesystems by sorting discovered paths.

### 5) Risk Assessment

**MEDIUM** — The design is solid, but packaging and secret-scanner interactions are practical footguns.

---

## Overall Phase 4 Plan Set

- The sequence (04-01 skeleton → 04-02 persistence/interrupts/logging → 04-03 skills adapter) is logically correct.
- The biggest cross-plan risk is 04-02's unresolved checkpoint identity/thread identity/DB-write-boundary story. Tighten that design early with a spike and a documented contract.
- Second biggest risk is resource shipping for skills; easy to miss until the CLI is installed outside the repo.

**Overall risk level: HIGH**, driven primarily by 04-02 foundational uncertainties. If resolved with an early spike and a documented threading/checkpoint contract, it drops to MEDIUM.

---

## OpenCode Review

# Cross-AI Plan Review: Phase 4 Plans

## Summary

The three Phase 4 plans establish the LangGraph runtime foundation, persistent checkpointing with first-class interrupts, and an Agent Skills adapter. Plan 04-01 delivers the state graph and five thin agent nodes. Plan 04-02 adds SqliteSaver persistence, interrupt handling for safety/cost commands, and activation logging. Plan 04-03 ships the skills adapter with 14 first-slice `SKILL.md` files. Together they satisfy GRAPH-01 through GRAPH-05 and SKILL-01 through SKILL-05.

Overall the plans are well-structured with clear dependencies and threat mitigations. However, there are execution-ordering risks and design concerns worth noting.

---

## Plan 04-01-PLAN.md: LangGraph Runtime Foundation

### Strengths

- **Clean separation of concerns**: TypedDict mirror (`SagaGraphState`) over Pydantic `SagaState` keeps validation at persistence boundaries without per-node Pydantic overhead.
- **Import-time guards**: Field-drift assertion and `PHASE_TO_ENTRY` exhaustiveness check catch schema evolution errors early.
- **Thin-node rule enforced**: Tests explicitly verify nodes are pure functions with no I/O.
- **Proper phase routing**: Maps `onboarding`/`character_creation` to onboarding node, `play`/`combat` to oracle chain, and `paused`/`session_end` to END.

### Concerns

1. **MEDIUM — `pending_narration` field added implicitly:** Task 2 adds `pending_narration` to both `SagaGraphState` and `SagaState` but describes it as implicit via test 8. The field addition should be explicit in task deliverables and summary.
2. **MEDIUM — Combat phase routing:** The plan states `combat` differs in payload, not graph shape, but does not implement combat-specific routing or handling. Validate this assumption against PF2E_MVP_SUBSET.md before Phase 5.
3. **LOW — Schema drift guard timing:** If `SagaGraphState` is imported before `SagaState` in unusual import orders, the guard behavior should remain explicit and deterministic.
4. **LOW — Empty test package `__init__.py` files:** Harmless but likely unnecessary.

### Risk Assessment

**LOW** — Plan 04-01 is a foundational skeleton with solid routing exhaustiveness tests. Main risk is contained scope creep.

---

## Plan 04-02-PLAN.md: Persistent Graph with Checkpoints and Interrupts

### Strengths

- **SqliteSaver integration**: Correctly uses the existing campaign connection to share transaction scope with `turn_close`.
- **Interrupt envelope pattern**: Clean abstraction via `InterruptKind` enum and `InterruptEnvelope` dataclass.
- **Dual SafetyEvent + Interrupt writes**: Preserves Phase 3 `/pause` and `/line` SafetyEvent logging while adding interrupt plumbing.
- **Turn-close integration**: Archivist node calls injected `turn_closer`, ensuring final checkpoint happens in the same SQLite transaction.

### Concerns

1. **HIGH — Pre-narration checkpoint recording is fragile:** The plan says the caller inspects `graph.get_state(config)`, extracts a checkpoint ID, and writes a `CheckpointRef` row. This is error-prone because the TUI caller must remember to write it, and a crash between interrupt and ref write leaves no pre-narration ref. Move `record_pre_narration_checkpoint` into graph/runtime boundary code with a single owner, rather than leaving it to arbitrary callers.
2. **HIGH — SqliteSaver schema collision needs explicit CI protection:** The threat model notes table collisions, but the plan should include an explicit test that fails if SagaSmith tables collide with known LangGraph tables.
3. **MEDIUM — Activation logger contextvar ordering:** Plan 04-02 creates the logger wrapper, but Plan 04-03 introduces the contextvar handoff. To avoid a cross-plan gap, include a contextvar stub in 04-02 or make 04-02 tests assert `skill_name IS NULL` only. (Note: the current Plan 04-02 text does state `skill_name` is NULL for this plan; the concern is about avoiding accidental test expectations.)
4. **MEDIUM — Budget stop translation:** Wrapping `BudgetStopError` in nodes while using placeholder `0.0` estimates means the path will not fire meaningfully until Phase 6.
5. **LOW — Single interrupt slot overwrites:** If a player types `/retcon` while already paused, the first interrupt is lost. Document user impact.

### Risk Assessment

**MEDIUM** — The checkpoint recording pattern is the weakest link. Other concerns are manageable with explicit mitigations.

---

## Plan 04-03-PLAN.md: Agent Skills Adapter

### Strengths

- **Zero new dependencies**: Hand-rolled frontmatter parser keeps the adapter lightweight.
- **Redaction canary integration**: Consistent with Phase 3 safety patterns.
- **Authorization enforcement**: `load_skill` checks `allowed_agents` before returning.
- **First-slice coverage**: The plan ships the intended 14 skills with valid frontmatter and structured bodies.
- **Deterministic handlers**: Skills with `implementation_surface: deterministic` have working handlers wired into nodes.

### Concerns

1. **MEDIUM — Hand-rolled frontmatter parser limitations:** The parser rejects multi-line descriptions. If any prompted skill needs richer metadata, this will break. Consider allowing escaped newlines or document the strict subset.
2. **MEDIUM — Skill count for first slice:** Shipping 14 skills is aggressive. Several are marked `first_slice: false` but still included. Clarify required versus optional skills for the vertical slice.
3. **MEDIUM — Contextvar handoff complexity:** The `get_current_activation().set_skill()` pattern adds indirection. Since it depends on single-threaded assumptions, document the constraint to prevent future parallelization mistakes.
4. **LOW — `first_slice_only` filter should be a first-class schema field:** Add `first_slice: bool` to frontmatter and SkillRecord explicitly.
5. **LOW — SkillStore error surfacing:** `SkillStore.errors` is collected, but the plan does not specify how developers see these errors at startup or via diagnostics.

### Risk Assessment

**LOW** — The adapter is well-designed and follows ADR-0001 patterns. Main risk is parser brittleness, which the threat model acknowledges.

---

## Cross-Plan Concerns

### Dependency Ordering Issue

**CRITICAL — Activation logger/contextvar seam must be consistent:** Plans 04-02 and 04-03 meet at the activation logger. Plan 04-02 creates `AgentActivationLogger` and wraps nodes, while Plan 04-03 adds the contextvar that lets nodes set active skill names. Ensure 04-02's tests expect `skill_name` to remain NULL until 04-03, or add the contextvar stub in 04-02 to prevent later churn.

### SqliteSaver + Turn Close Transaction Scope

The plan correctly notes that both SqliteSaver and `turn_close` use the same connection, but it does not specify transaction isolation level. Explicitly verify the connection’s isolation behavior and the order of turn-close commit versus checkpoint writes.

### Test Coverage Gap

Plan 04-02 simulates incomplete-turn resume, but should also verify state equivalence after resume versus a fresh run. This is critical for `PERSISTENCE_SPEC.md §5` compliance.

---

## Suggestions Summary

| Plan | Priority | Suggestion |
|------|----------|------------|
| 04-01 | MEDIUM | Make `pending_narration` field addition explicit in artifacts and summaries. |
| 04-02 | HIGH | Make pre-narration checkpoint ref writing owned by one graph/runtime boundary, not arbitrary caller responsibility. |
| 04-02 | HIGH | Add explicit CI test for SqliteSaver table-name collision detection. |
| 04-02 | MEDIUM | Include contextvar stub or assert `skill_name IS NULL` until 04-03. |
| 04-03 | MEDIUM | Document or slightly expand frontmatter parser capabilities. |
| 04-03 | LOW | Add `first_slice` as a proper frontmatter and `SkillRecord` field. |

---

## Risk Assessment Summary

| Plan | Overall Risk | Justification |
|------|--------------|---------------|
| 04-01 | LOW | Clean foundation, well-tested. |
| 04-02 | MEDIUM | Checkpoint recording pattern is fragile; activation logger/contextvar seam needs consistency. |
| 04-03 | LOW | Well-designed adapter with solid threat mitigations. |

**Combined Phase 4 Risk: MEDIUM.** The primary blocker is the checkpoint recording pattern in Plan 04-02. The other plans are solid, but the inter-plan activation logger/contextvar seam should be made explicit before proceeding.

---

## Consensus Summary

### Agreed Strengths

- **Typed graph-state adapter is strong.** All reviewers praised the `SagaState` ↔ `SagaGraphState` TypedDict/Pydantic boundary, especially the field-drift guard and routing exhaustiveness checks.
- **Thin-node/service-injection pattern is the right architectural boundary.** Reviewers agreed that keeping SQL, HTTP, LLM, and vault I/O out of node bodies preserves testability and deterministic replay.
- **The phase sequencing is logical.** Skeleton graph → persistent checkpoints/interrupts/logging → skills adapter is a coherent dependency chain.
- **Security and audit posture is strong.** Reviewers consistently highlighted RedactionCanary usage, activation logging, and explicit interrupt taxonomy as valuable.
- **TDD detail is unusually strong.** Behavior-numbered tests, migration tests, and no-paid-call verification were praised across reviewers.

### Agreed Concerns

1. **Plan 04-02 is the highest-risk plan.** Multiple reviewers flagged checkpoint/interrupt semantics, checkpoint ref ownership, LangGraph native interrupt usage, and checkpoint/thread identity as unresolved architectural risks.
2. **Pre-narration checkpoint metadata needs a single reliable owner.** Reviewers agreed that relying on “caller inspects state and writes a ref” is fragile; the plan should specify one graph/runtime boundary responsible for `CheckpointRef(kind="pre_narration")`.
3. **Schema evolution needs explicit handling.** `pending_narration` and `pending_interrupt` expand `SagaState`/JSON Schema and require fixture, schema-export, and downstream contract updates.
4. **Task granularity is too coarse.** Claude and Codex especially judged the two-task structure for 04-02 and 04-03 as under-scoped for the implementation surface.
5. **Agent Skills adapter details need tightening.** Reviewers agreed on documenting YAML-lite limitations, making `first_slice`/`first_slice_only` first-class, and avoiding brittle exact-count tests.
6. **Packaged skill resources must be included in built distributions.** Codex uniquely emphasized this, but it is a concrete release footgun: `SKILL.md` files need package-data config and an installed-style test.

### Divergent Views

- **Overall risk level varied.** Gemini rated the phase LOW, OpenCode MEDIUM, Claude MEDIUM–HIGH, and Codex HIGH. The difference is mostly due to how much uncertainty each reviewer assigned to Plan 04-02’s LangGraph checkpoint/interrupt assumptions.
- **`pending_interrupt` as state field.** Gemini accepted the pattern with payload-size caveats; Claude and Codex recommended preferring LangGraph native interrupt primitives or documenting a deliberate deviation.
- **Exact skill count assertion.** Claude saw the `== 14` gate as a strong CI check; Codex saw it as brittle and suggested required-set containment instead.
- **ContextVar handoff.** Most reviewers accepted it as practical under the current single-threaded constraint, but OpenCode and Gemini recommended documenting concurrency assumptions, and Claude noted it could become fragile if graph execution becomes parallel.

### Top Planning Changes to Feed Back Into `/gsd-plan-phase 4 --reviews`

1. **Add a LangGraph spike/contract before implementing 04-02:** prove `interrupt_before`, `Command(resume=...)`, checkpoint ID availability, and whether `thread_id` should be campaign-scoped or turn-scoped.
2. **Revise 04-02 checkpoint ownership:** make pre-narration `CheckpointRef` writing the responsibility of one graph/runtime boundary and test crash/recover equivalence.
3. **Keep DB writes and budget-stop conversion out of node bodies:** use wrappers/services so thin-node invariants remain true.
4. **Make schema additions explicit:** add `pending_narration`, `pending_interrupt`, JSON Schema export updates, and fixture updates as named tasks.
5. **Split oversized tasks:** especially 04-02 Task 2 and 04-03 Task 2.
6. **Make skills packaging and filtering explicit:** include `SKILL.md` files as package data, add installed-style tests, add `first_slice` to `SkillRecord`, and use required-set assertions instead of only exact counts.
7. **Add a minimal end-to-end TUI input → graph turn → stub narration smoke test** so Phase 4 proves the graph is not just constructed but invokable from gameplay control flow.
