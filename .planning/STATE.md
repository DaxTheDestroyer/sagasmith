---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Phase 8 review fixes complete
last_updated: "2026-04-29T19:20:00Z"
last_activity: 2026-04-29 -- Fixed Phase 8 review issues and restored release-gate component checks
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 35
  completed_plans: 35
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-26)

**Core value:** A solo player can start, play, quit, and resume an AI-run PF2e campaign where the story adapts to their choices while rules, memory, safety, cost, and persistence remain trustworthy.
**Current focus:** Phase 8 — Retcon, Repair, and Release Hardening

## Current Position

Phase: 8 of 8 (Retcon, Repair, and Release Hardening) — All plans complete (08-01, 08-02, 08-03, 08-04)
Plan: All complete
Status: Phase 8 complete — retcon audit/persistence, RetconService/runtime rollback, TUI retcon UI, and MVP smoke/release gate implemented
Last activity: 2026-04-29 -- Fixed Phase 8 review issues: canonical retcon transcript reads, stale docs/tests, typecheck, formatting, full tests, MVP smoke, and secret scan

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 35
- Average duration: 22 min
- Total execution time: ~6.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Contracts, Scaffold, and Eval Spine | 3 | 3 | 22 min |
| 2. Deterministic Trust Services | 6 | 6 | -- |
| 3. CLI Setup, Onboarding, and TUI Controls | 4 | 4 | -- |
| 4. Graph Runtime and Agent Skills | 5 | 5 | ~35 min |
| 5. Rules-First PF2e Vertical Slice | 5 | 69 min | 14 min |
| 6. AI GM Story Loop | 7 | ~115 min | ~16 min |
| 7. Memory, Vault, and Resume Differentiator | 1 | -- | -- |
| 8. Retcon, Repair, and Release Hardening | 4 | 28 min | ~7 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Recent decisions affecting current work:

- [Roadmap]: Standard granularity uses 8 phases to preserve clean SagaSmith delivery boundaries.
- [Roadmap]: Build order follows trust-before-breadth: contracts, deterministic services, TUI/onboarding, graph/skills, rules slice, AI loop, memory/vault, hardening.
- [02-01]: SecretRef uses BaseModel directly (not SchemaModel) to avoid circular imports with schemas/provider.py.
- [02-04]: CostGovernor uses TYPE_CHECKING for TokenUsage import to prevent circular imports at module load time.
- [02-06]: SQLite implicit transaction semantics replace explicit BEGIN in close_turn to avoid "cannot start a transaction within a transaction".
- [03-plan]: Phase 3 split into 4 plans across 3 waves: 03-01 (campaign+CLI, Wave 1) and 03-02 (onboarding, Wave 1) run parallel, 03-03 (TUI shell, Wave 2) depends on 03-01, 03-04 (commands+safety, Wave 3) depends on 03-02 + 03-03.
- [03-plan]: `/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/retcon` ship as narration-emitting stubs in Plan 03-04; each stub names its owning future phase (Phase 4/5/7/8) so later plans can locate the replacement site without code archaeology.
- [03-01]: Hand-rolled TOML writer in campaign.py to avoid tomli_w dependency.
- [03-01]: SettingsRepository.put always runs RedactionCanary scan before INSERT/UPDATE, mirroring turn_close.py invariant.
- [03-02]: StrEnum used for OnboardingPhase/PromptFieldKind (ruff UP042 fix, Python 3.11+ StrEnum).
- [03-03]: textual>=0.79,<1 upper bound to avoid 1.x API churn.
- [03-03]: RichLog(markup=False) for NarrationArea — prevents Rich markup injection from transcript content (T-03-17).
- [03-03]: CommandRegistry is the only extension point; --headless-status flag preserves CLI test contract.
- [03-04]: PEP 562 __getattr__ in services/__init__.py breaks circular import chain services → safety → evals → fixtures → schemas → campaign → services.
- [03-04]: SafetyEventService._canary uses _default_canary() factory (deferred import) rather than module-level import.
- [03-04]: NarrationArea.logged_lines is public (no leading _) for pyright compliance in tests.
- [03-04]: service_conn single long-lived SQLite connection in build_app() — Textual single-threaded; Phase 4 will revisit for concurrent checkpointing.

### Pending Todos

- None — all Phase 8 plans (08-01 through 08-04) are complete. All 35 plans across all 8 phases are done.

### Blockers/Concerns

- None currently. All Phase 8 plans are complete.

### Decisions (continued from Phase 4)

- [04-01]: SagaGraphState TypedDict mirror with import-time field-drift guard prevents silent schema regressions.
- [04-01]: PHASE_TO_ENTRY uses END sentinel (not str) for terminated phases; combat routes to END in Phase 4, Phase 5 adds sub-routing.
- [04-02]: Thread identity locked to `campaign:<campaign_id>`; turn_id stays in state + checkpoint_refs.
- [04-02]: Pre-narration and final CheckpointRef writes owned by GraphRuntime boundary, not nodes or TUI.
- [04-02]: AgentActivationLogger uses ContextVar for skill_name injection without re-plumbing node signatures.
- [04-03]: Native LangGraph update_state + Command(resume) for interrupts; nodes remain interrupt-agnostic.
- [04-03]: BudgetStopError translation lives ONLY in runtime wrapper.
- [04-03]: RetconCommand acknowledge-only in Phase 4; Phase 8 owns full confirmation + rollback.
- [04-04]: YAML-lite hand-rolled parser (no PyYAML dependency) with documented SUPPORTED_SUBSET.
- [04-04]: Agent-scoped skills with `allowed_agents: ["*"]` are REJECTED, not silently downgraded.
- [04-04]: Deterministic scan order via `sorted(Path.rglob("SKILL.md"))`.
- [04-05]: _default_skill_store() raises loud on production scan errors at startup.
- [04-05]: ContextVar handoff pattern: nodes call `get_current_activation().set_skill(...)` when activation is present.
- [05-01]: RulesEngine rejects unsupported stat names before rolling so player input cannot trigger hidden fields or unsupported mechanics.
- [05-01]: CombatantState carries defaulted first-slice enemy mechanics fields so enemy data validates as typed models while existing callers remain compatible.
- [05-02]: CombatEngine returns both Strike CheckResult and optional damage RollResult so downstream roll-log persistence can store the attack and exactly one damage roll_id.
- [05-02]: First-slice melee targeting validates target position and fails before action consumption or rolling when range is invalid.
- [05-03]: RulesLawyer accepts only anchored first-slice command forms and returns deterministic `Rules error:` narration for unsupported input rather than silent `{}`.
- [05-03]: Combat phase routes to RulesLawyer and the compiled graph START branch includes `rules_lawyer` as a destination.
- [05-03]: TUI play-state construction seeds the first-slice pregen only when no sheet exists, preserving live HP/combat mutations.
- [05-04]: `/sheet` reads live graph `character_sheet` state first and falls back to the first-slice factory only when live data is absent or invalid.
- [05-04]: Reveal-mode dice details are transcript-rendered from existing `CheckResult` values and omit modal pre-prompts/dismissal hints in Phase 5.
- [05-04]: Combat status rendering uses typed `CombatState` and handles zero, one, or two enemies without fixed encounter assumptions.
- [05-05]: Sequential Textual rules inputs preserve graph mechanics state so `/sheet`, skill checks, combat start, turn advancement, and Strikes can be regression-tested without paid calls.
- [05-05]: QA-03 coverage is scenario-driven through deterministic services rather than a hardcoded label-set assertion.
- [05-05]: Smoke harness registration uses a provider-free `rules_first_vertical_slice` check for sheet, skill, initiative, and Strike mechanics.
- [06-05]: Phase 6 memory assembly is transcript-only and provider-free; full vault/search retrieval remains deferred to Phase 7.
- [06-05]: `memory-packet-assembly` is first-slice safe and is the Archivist skill logged during Phase 6 turn flow.
- [06-05]: `GraphRuntime` injects the SQLite transcript connection into `AgentServices` so agent nodes remain pure while memory logic can read recent transcript rows.
- [06-01]: Worldgen Agent Skills are future-scoped (`first_slice: false`) and run only when an LLM client is injected, preserving no-paid-call behavior.
- [06-01]: Oracle stores `world_bible` and `campaign_seed` idempotently; re-entry skips generation once both fields exist.
- [06-01]: Prompt modules live under `src/sagasmith/prompts/oracle/` with `PROMPT_VERSION`, `SYSTEM_PROMPT`, `build_user_prompt`, and `JSON_SCHEMA` per D-06.5.
- [06-03]: RulesLawyer LLM fallback classifies only action shape; deterministic services rebuild CheckProposal math from trusted state.
- [06-03]: Non-mechanical player input returns no RulesLawyer update so narration can proceed without a visible rules error.
- [06-03]: Intent LLM unavailability or budget exhaustion degrades to deterministic-only routing instead of failing the turn.
- [06-02]: SceneBrief keeps readable `beats` and adds parallel `beat_ids` for explicit Orator resolution tracking.
- [06-02]: Oracle replans only when no brief exists, all active beat IDs are resolved, or player-choice branching detects bypass/rejection/reframe.
- [06-02]: Scene intent pre-gate routing is deterministic skill-level logic now; full Task 7 safety service/post-gate regression remains separate.
- [06-04]: SafetyPostGate from 06-07 is reused directly; Orator pipeline does not duplicate the service.
- [06-04]: Inline hard-limit matcher runs on accumulated buffer text every 50 tokens, not per-token, to catch multi-word patterns during streaming.
- [06-04]: Mechanical-consistency audit uses deterministic degree-of-success keyword tables; no second LLM verifier in Phase 6 (D-06.2).
- [06-04]: Beat resolution uses keyword overlap heuristic between narration and beat text; actor_id parameter reserved for Phase 7 per-actor filtering.
- [06-04]: Two-rewrite budget shared between post-gate blocks/rewrites and mechanics audit failures.
- [07-04]: Hyphenated Agent Skill directories wrap underscore Python packages so skill discovery names remain stable while imports remain valid.
- [07-04]: Canon-conflict detection is a non-blocking warning stub until full extraction/routing is implemented.
- [07-05]: Player-vault sync rebuilds the player projection from scratch to remove stale spoiler files.
- [07-05]: `/recap` is deterministic and provider-free, reading graph rolling_summary plus SQLite transcript rows.
- [08-01]: Retconned rows are retained for audit but excluded from canonical turn/transcript helpers by default.
- [08-01]: Vault-write audit records are inserted only after successful master-vault writes.
- [08-02]: Retcon preview blocks unless the selected turn is complete and a prior final checkpoint exists.
- [08-02]: Retcon confirmation commits retconned statuses and audit rows before derived rebuild/sync so future canonical reads already exclude affected turns if repair is needed.
- [08-02]: Runtime retcon completion messages reference only turn ids/counts and avoid removed canon details.
- [08-04]: MVP smoke uses deterministic in-process services and fake provider configuration, never OpenRouter credentials.
- [08-04]: Release-gate secret scanning uses the existing pre-commit gitleaks hook.
- [08-03]: /retcon no-arg lists recent eligible completed turns; never silently targets latest turn.
- [08-03]: Confirmation uses exact turn-specific token `RETCON {turn_id}` parsed from joined command args.
- [08-03]: sync_after_retcon() resyncs narration and mechanics after successful retcon without exiting the app.
- [08-03]: Both success and blocked messages restrict output to turn ids/counts and repair guidance; never expose removed transcript content.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Integration | 06-08: full-turn-flow + safety-enforcement integration tests (`test_full_turn_flow.py`, `test_safety_enforcement.py`) | Deferred | 2026-04-28 (Phase 6) |
| Session pages | 07-04: `session_page_authoring` permanently emits `quests_closed=[]` and `callbacks_paid_off=[]`; real inference requires canonical quest/callback state tracking | Deferred | 2026-04-29 (Phase 7) |
| Visibility | 07-04: `visibility_promotion` uses substring match on entity name/alias; short names may cause false promotion | Deferred | 2026-04-29 (Phase 7) |

## Session Continuity

Last session: 2026-04-29T17:35:00Z
Stopped at: Phase 8 review fixes complete; all Phase 8 plans (08-01 through 08-04) complete
Resume file: None
