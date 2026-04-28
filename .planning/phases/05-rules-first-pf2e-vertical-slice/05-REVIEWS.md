---
phase: 5
reviewers: [gemini, claude, codex, opencode]
reviewed_at: 2026-04-27T20:01:49.0664811-06:00
plans_reviewed:
  - .planning/phases/05-rules-first-pf2e-vertical-slice/05-01-PLAN.md
  - .planning/phases/05-rules-first-pf2e-vertical-slice/05-02-PLAN.md
  - .planning/phases/05-rules-first-pf2e-vertical-slice/05-03-PLAN.md
  - .planning/phases/05-rules-first-pf2e-vertical-slice/05-04-PLAN.md
  - .planning/phases/05-rules-first-pf2e-vertical-slice/05-05-PLAN.md
---

# Cross-AI Plan Review - Phase 5

## Review Run Notes

Available CLIs detected: Gemini, the agent, Codex, OpenCode.

Unavailable CLIs: CodeRabbit, Qwen, Cursor.

Codex invocation failed because the installed Codex CLI rejected the configured `gpt-5.5` model as requiring a newer CLI. A fallback `--model gpt-5.1` retry still used the configured model and failed the same way. The failure is preserved below.

OpenCode produced partial output only. The partial review is preserved below.

## Gemini Review

# Phase 5 Plan Review: Rules-First PF2e Vertical Slice

## Overview

The Phase 5 plans collectively define a robust, deterministic foundation for Pathfinder 2e mechanics, adhering strictly to the constraints of no LLM-authored math and a purely terminal-based TUI. The separation of data/rules engines (05-01, 05-02), graph routing (05-03), TUI updates (05-04), and end-to-end evaluation (05-05) is well-architected. However, there are significant UX risks regarding exact-string text parsing and minor logic gaps in combat state resets.

### Plan 05-01: First-Slice Rules Foundation

**Summary**: This plan implements the foundational rules engine and hardcoded data for the Phase 5 vertical slice, including a pregen martial character, basic enemy records, and skill/Perception check resolution using the existing `DiceService`.

**Strengths**

- Pure functions for data factory generation ensure immutability and stable testing.
- Clear separation of deterministic rules from LLM logic.
- Directly leverages the existing `DiceService` and `compute_degree` to guarantee auditable, replayable rolls.

**Concerns**

- **MEDIUM**: Unsupported stats raise `ValueError`. This is correct internally, but if these exceptions are not caught and handled gracefully in the upstream graph or TUI, they could crash the application.
- **LOW**: Character and enemy data are hardcoded in Python files rather than externalized schemas. This is acceptable for a vertical slice but introduces tech debt for future content expansion.

**Suggestions**

- Explicitly define how `ValueError`s raised by `RulesEngine` should be handled, such as catching them in the `RulesLawyer` node and returning a user-friendly error state.
- Ensure `CheckProposal` is appropriately logged if required by `STATE_SCHEMA.md`, alongside `CheckResult`.

**Risk Assessment**: **LOW**. The scope is tightly bounded, purely functional, and builds on existing tested primitives.

### Plan 05-02: First-Slice Combat Mechanics

**Summary**: This plan introduces the `CombatEngine` to manage theater-of-mind combat, handling initiative, action economy, simplified positional tracking, and Strike resolution with deterministic damage.

**Strengths**

- Strictly limits scope to the four approved positions and enforces the two-enemy limit.
- Effectively models state transitions without mutating inputs, returning updated `CombatState` objects.

**Concerns**

- **MEDIUM**: Hardcoding Strike damage to deterministic flat values instead of rolling dice is a notable deviation from PF2e rules. While `DiceService` currently only supports d20s, this shortcut should be explicitly documented as Phase 5 tech debt.
- **MEDIUM**: `end_turn` specifies resetting actions to 3 but omits resetting `reaction_available` to `True` for the new active combatant or at the start of a round.
- **MEDIUM**: Raising `ValueError` for invalid melee range or zero actions needs a clear catch mechanism in the caller to provide TUI feedback rather than a crash.

**Suggestions**

- Explicitly mandate that `end_turn` or round advancement resets `reaction_available = True`.
- Document the fixed damage values as a temporary Phase 5 crutch, noting that a `roll_damage` function will be required in the future.

**Risk Assessment**: **MEDIUM**. State mutation for combat is complex, and relying on `ValueError` for rule enforcement requires careful upstream handling.

### Plan 05-03: RulesLawyer Graph Integration

**Summary**: This plan integrates the deterministic engines into the LangGraph `RulesLawyer` node, replacing LLM-based parsing with strict string matching for player commands, and routes the combat phase appropriately.

**Strengths**

- Explicitly tests that `services.llm` is not called, strictly enforcing the Phase 5 safety boundary.
- Successfully seeds the graph state with the pregen character sheet.

**Concerns**

- **HIGH**: The parser relies on exact string matching. If a user types `roll Athletics DC 15` or uses an alias for a target, the command will silently fail by returning `{}`.
- **MEDIUM**: Unsupported input returning `{}` gives the user no feedback on why the action failed or what syntax is expected.
- **MEDIUM**: If `CombatEngine` raises a `ValueError`, returning `{}` or crashing are both poor outcomes.

**Suggestions**

- Implement case-insensitive parsing and strip extra whitespace for commands.
- If parsing fails or a rules engine raises an exception, return a deterministic error message in state so the TUI can display it instead of silently ignoring input.

**Risk Assessment**: **MEDIUM**. The fragile text parser is a major UX risk for a text-driven application and needs robust error-feedback mechanisms.

### Plan 05-04: TUI Mechanics Surfaces

**Summary**: This plan implements the Textual TUI surfaces for Phase 5: the `/sheet` command, the dice reveal overlay, and the combat-aware status panel, adhering strictly to the plain-text UI-SPEC.

**Strengths**

- Adheres tightly to the UI-SPEC, avoiding over-engineered UI components.
- Extracts renderers into pure functions, maximizing testability.
- Ensures all essential mechanic information is readable as text, without relying on color-only cues.

**Concerns**

- **MEDIUM**: If the `RulesLawyer` node pre-computes the `CheckResult` and updates graph state, the status panel might show the roll outcome before the dice overlay is dismissed, ruining reveal suspense.
- **LOW**: The dice overlay prompt says `Press Enter to roll` even though the result may already be pre-computed.

**Suggestions**

- Ensure the TUI delays updating last rolls and HP values until after the reveal modal for that `roll_id` has been dismissed.
- Clarify the overlay prompt to say `Press Enter to reveal` if the roll is already pre-computed.

**Risk Assessment**: **LOW**. Standard TUI updates, provided state synchronization respects reveal timing.

### Plan 05-05: Integration and Verification

**Summary**: This plan adds the required end-to-end smoke tests and QA-03 evaluation gates to prove the vertical slice works without paid LLM calls.

**Strengths**

- Explicitly maps to QA-03 requirements and tests them comprehensively.
- Uses deterministic fake services to ensure the smoke harness runs reliably offline and without cost.

**Concerns**

- **LOW**: Integration tests are highly dependent on exact UI strings, which may create brittle tests for future UI tweaks.

**Suggestions**

- Keep string assertions as flexible as possible by checking key substrings rather than exact full-line matches.

**Risk Assessment**: **LOW**. The testing strategy is sound and effectively acts as a solid quality gate for the phase.

### Overall Phase 5 Assessment

**Overall Risk: MEDIUM**

The architectural split between deterministic code and LLM agents is excellent and aligned with the project's goals. The primary risks are integration boundaries: exact-string parsing of player commands and handling internal validation errors from `CombatEngine`. If parser failures are silent or validation errors crash the app, the vertical slice will feel broken. Addressing parser fragility and user-friendly error mapping would lower the overall risk.

---

## the agent Review

# Phase 5 Plan Review - Rules-First PF2e Vertical Slice

## Overall Summary

The five plans together form a coherent, well-scoped implementation strategy that follows the deterministic-first architecture mandate. Wave decomposition is sensible, dependencies are explicit, and the no-LLM-math boundary is enforced through structural choices. However, several plans rely on hardcoded magic values for damage, render `/sheet` from a freshly-built sheet rather than current state, treat the QA-03 gate as label-listing rather than behavior coverage, and underspecify reveal-mode modal interaction and roll-log persistence. None are fatal, but they should be addressed before execution.

### Plan 05-01: Rules Foundation

**Strengths**

- Tight separation of data helpers from `RulesEngine.resolve_check`.
- Explicit `proposal_id` formula supports deterministic replay.
- Fail-closed unsupported stat behavior happens before rolling.
- No need for `services.llm` in the mechanics path.

**Concerns**

- **MEDIUM**: `make_first_slice_enemies()` returns `tuple[dict[str, object], ...]` rather than typed `CombatantState` instances. If the data is not pre-validated, type errors land in combat construction.
- **MEDIUM**: Save values are not pinned. UI-SPEC requires the sheet to render Fortitude, Reflex, and Will, but the plan does not specify `saving_throws` values.
- **LOW**: No assertion that the sheet round-trips through `model_dump` and model validation.
- **LOW**: `kind` is limited to `Literal["skill", "initiative"]`; Strike handling diverges rather than sharing a single check taxonomy.

**Suggestions**

- Return validated `CombatantState` objects from `make_first_slice_enemies()` or specify a `TypedDict` shape.
- Pin Fortitude, Reflex, and Will modifiers in the plan behavior.
- Add a `CharacterSheet.model_validate(sheet.model_dump())` round-trip test.

**Risk**: **LOW**

### Plan 05-02: Combat Engine

**Strengths**

- Enemy cap is enforced structurally.
- Position tags are constrained to a closed set.
- Initiative `CheckResult` records produce auditable rolls.
- Strike error messages match UI-SPEC copy.

**Concerns**

- **HIGH**: Damage values are hardcoded literals rather than rolled through `DiceService`. This conflicts with the expectation that every mechanical roll is logged. The d20 attack roll appears in the log; the damage roll does not.
- **HIGH**: Initiative tie-breaking is unspecified. Sorted descending is insufficient when totals tie.
- **MEDIUM**: `end_turn` does not define behavior for defeated combatants at 0 HP.
- **MEDIUM**: Multiple Attack Penalty is absent. If intentionally out of scope, the plan should explicitly defer it.
- **MEDIUM**: Ranged Strike range rules are underspecified for all four position tags.
- **LOW**: `reaction_available` is tracked but never consumed.
- **LOW**: `move` accepts any of the four positions but does not model adjacency or multi-action distance changes.

**Suggestions**

- Roll damage through a deterministic dice primitive or explicitly document fixed damage as a first-slice simplification and audit limitation.
- Specify initiative tiebreakers, such as higher Perception modifier then actor ID.
- Specify how `end_turn` handles defeated combatants.
- Add a complete ranged Strike position matrix.

**Risk**: **MEDIUM**

### Plan 05-03: Graph and Agent Wiring

**Strengths**

- Removes `_TRIGGER_PHRASES` and replaces it with a closed-set matcher.
- Tests inject an LLM object that raises on touch, providing strong no-LLM enforcement.
- Combat routing change is small and clear.
- Local import of `make_first_slice_character` keeps TUI module coupling low.

**Concerns**

- **MEDIUM**: Pattern parsing rules are ambiguous. The behavior says inputs containing a stat and DC should resolve, while the action block lists exact patterns. Pick one, preferably anchored regexes.
- **MEDIUM**: State key contract is not verified for `check_results` and `combat_state` in the Phase 4 `SagaState` shape.
- **MEDIUM**: Combat completion routing is unowned. When `is_encounter_complete` is true, the plan does not say whether `phase` returns to `play`.
- **LOW**: `_build_play_state` may overwrite the character sheet if it is called per turn; verify it only seeds session start or preserves existing sheet state.
- **LOW**: Conditional `combat-resolution` skill activation is vague.

**Suggestions**

- Replace loose wording with anchored, case-normalized regex patterns and assert those in tests.
- Add or verify `check_results` and `combat_state` in `SagaState`.
- Add a sub-step to flip phase back to `play` when combat completes.

**Risk**: **MEDIUM**

### Plan 05-04: TUI Surfaces

**Strengths**

- Pure rendering functions avoid rolling or state mutation.
- Negative acceptance criteria prevent the dice overlay from importing rolling services.
- Exact UI-SPEC strings are copied into the plan.
- Status panel extension preserves existing layout.

**Concerns**

- **HIGH**: `/sheet` renders `make_first_slice_character()` directly, not the current sheet from app state. After combat changes PC HP, `/sheet` can show pristine 20/20 HP while status shows damaged HP.
- **HIGH**: Reveal-mode keyboard interaction is not implemented. If transcript rendering is intended instead of modal behavior, the plan should make that explicit and avoid misleading `Press Enter` copy.
- **MEDIUM**: `format_combat_status` enemy line is specified as a fixed two-enemy template; one-enemy and zero-enemy cases are unspecified.
- **MEDIUM**: Accepting `CombatState | dict[str, object] | None` loses type safety at the rendering boundary.
- **LOW**: `Actions: {remaining}/3` does not explicitly identify the active combatant.

**Suggestions**

- Have `SheetCommand.handle` resolve the sheet from app state first, falling back to the factory only if absent.
- Explicitly choose modal versus transcript-rendered reveal mode and align text accordingly.
- Specify zero, one, and two enemy combat-status rendering.

**Risk**: **MEDIUM**

### Plan 05-05: Verification Spine

**Strengths**

- End-to-end test exercises TUI/graph composition.
- Negative assertion against `OpenRouterClient` helps prevent paid calls.
- Adds a `rules_first_vertical_slice` smoke harness entry.

**Concerns**

- **HIGH**: The QA-03 coverage gate is self-referential if it only asserts that hardcoded labels exist in a hardcoded set. It should invoke representative scenarios or discover coverage through markers/function names.
- **MEDIUM**: Roll-log persistence is not tested across a checkpoint or quit/resume cycle. RULE-11 and RULE-06 imply durable auditability and persisted initiative order.
- **MEDIUM**: Integration test assumes the PC is active after `start combat`; if an enemy wins initiative, the Strike may be rejected.
- **LOW**: Integration test does not pin the full UI-SPEC compact `[roll]` line.

**Suggestions**

- Replace label-only QA gate with scenario tests or coverage discovery tied to actual test functions.
- Add checkpoint/resume assertion for combat state, initiative order, and roll log.
- Seed dice to guarantee PC initiative or advance turns until the PC is active before Strike.

**Risk**: **MEDIUM**

### Cross-Plan Concerns

- **Roll log persistence is not explicitly addressed**. Plans build `CheckResult` and `RollResult` data, but durable audit log persistence is not clearly tested.
- **Combat to play phase transition is unowned**.
- **Damage logging gap** is the largest divergence from the deterministic-first and RULE-11 mandate.
- **`/sheet` stale data** will become visible once combat changes HP.

### Overall Risk

**Overall Risk: MEDIUM**

The plans correctly enforce the no-LLM-math architecture and decompose the work cleanly. Risk is medium because three load-bearing issues need resolution before execution: hardcoded damage without roll-log entry, `/sheet` rendering from factory rather than state, and QA-03 as tautological label coverage.

---

## Codex Review

Codex review failed or returned empty output.

Error summary:

```text
OpenAI Codex v0.122.0 rejected the configured model.
The 'gpt-5.5' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.
```

A retry with `codex exec --model gpt-5.1 --skip-git-repo-check -` produced the same configured-model failure in this environment.

---

## OpenCode Review

OpenCode produced partial output only:

# Phase 5 Plan Review

## 05-01-PLAN.md: Deterministic Rules Foundation

**Summary**: Builds character/enemy data factories and skill/Perception check resolution - solid foundation work.

**Strengths**

- Clear separation between data helpers and rules engine.
- Uses existing DiceService and compute_degree correctly.
- TDD approach with explicit test assertions.

**Concerns**

- **MEDIUM**: Enemy data returns `dict[str, object]` but CombatEngine needs `CombatantState`-compatible records. Type alignment is needed in Task 1.
- **LOW**: Missing test for a skill not in the character's skill dict.

**Suggestions**: Add explicit cast/conversion to `CombatantState` in Task 1 acceptance criteria.

**Risk**: LOW

## 05-02-PLAN.md: Combat Engine

**Summary**: Implements initiative, action economy, positions, Strikes, and HP deltas - the most mechanically complex plan.

**Strengths**

- All core requirements covered: initiative, 3-action economy, positions, Strikes, HP, encounter completion.
- Range validation enforced.
- Output was truncated after this point.

---

## Consensus Summary

### Agreed Strengths

- The phase decomposition is coherent: rules data and checks first, combat second, graph/TUI wiring third, and verification last.
- The deterministic-services boundary is strong and aligned with the project architecture.
- The plans reuse existing `DiceService`, `compute_degree`, and Pydantic mechanics models instead of creating parallel mechanics paths.
- Tests are intentionally placed around no-LLM-math boundaries, including negative checks that `services.llm` is not used.
- The TUI work favors pure text renderers and testable functions rather than a broad UI rewrite.

### Agreed Concerns

- **HIGH: Damage and roll-log auditability are underspecified.** Multiple reviewers flagged fixed damage values as a potential conflict with RULE-11 and PF2e audit expectations. The plan should either add deterministic damage rolling/logging or explicitly document fixed damage as a deliberate Phase 5 simplification with compensating tests.
- **HIGH: `/sheet` should render live character state, not a fresh factory sheet.** Rendering `make_first_slice_character()` directly can show stale HP after combat. The command should prefer `app.state` or graph state and only fall back to the factory if no state exists.
- **HIGH: QA-03 coverage gate should test behavior, not labels.** A hardcoded set of QA labels can pass without proving degree boundaries, seeded replay, Strike, initiative, HP damage, or roll-log completeness. The gate should execute representative scenarios or verify real test coverage.
- **MEDIUM: Error handling and parser UX are weak.** Exact string matching, unsupported input returning `{}`, and uncaught `ValueError` paths can cause silent failures or crashes. Plans should specify case normalization, whitespace handling, anchored parsing, and deterministic user-visible error state.
- **MEDIUM: Combat edge cases need explicit ownership.** Initiative tie-breakers, defeated combatant turn skipping, reaction reset, combat completion route back to play, and ranged-position matrix are not fully specified.
- **MEDIUM: Roll-log and checkpoint persistence are not explicitly verified.** Plans return in-memory `CheckResult` data, but RULE-11 and RULE-06 imply persisted auditability and initiative order through checkpoints.
- **MEDIUM: Reveal-mode behavior is ambiguous.** The plan mixes static text rendering with modal language like `Press Enter to roll`. It should choose transcript-style reveal or modal interaction and update tests/copy accordingly.
- **MEDIUM: Enemy data typing is loose.** Returning `dict[str, object]` for enemies pushes validation errors into later combat setup. Reviewers recommended typed or validated enemy records.

### Divergent Views

- **Fixed damage values**: Gemini considered fixed values a medium-risk, acceptable vertical-slice shortcut if documented. The agent rated the issue high because it may violate roll-log and seeded-replay expectations.
- **Exact command parsing**: Reviewers agreed strict parsing is safe from an unsupported-mechanics standpoint, but disagreed on severity. Gemini emphasized UX fragility; the agent emphasized ambiguity in the plan wording and state-contract risks.
- **Reveal overlay implementation**: Gemini treated reveal timing as a low-to-medium synchronization issue. The agent treated lack of modal interaction as high unless transcript-only behavior is explicitly chosen.

### Recommended Plan Updates Before Execution

- Amend 05-02 to specify deterministic initiative tie-breakers, reaction reset, defeated-combatant handling, combat completion phase transition, and full ranged/melee position rules.
- Amend 05-02 or 05-05 to resolve fixed damage auditability: implement deterministic damage roll logging or document fixed damage as a Phase 5 simplification with explicit tests.
- Amend 05-03 to normalize and anchor command parsing, catch rules exceptions, return user-visible deterministic errors, and verify `check_results` and `combat_state` fit the current `SagaState` contract.
- Amend 05-04 so `/sheet` reads the current character sheet from state first, and clarify whether reveal mode is modal or transcript-rendered.
- Amend 05-05 so QA-03 invokes real behavior coverage and adds checkpoint/resume assertions for roll logs and initiative order.
