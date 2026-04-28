---
phase: 05-rules-first-pf2e-vertical-slice
plan: 03
subsystem: rules-graph
tags: [pf2e, rules-lawyer, combat, langgraph, tui, tdd]

requires:
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [deterministic RulesEngine checks, deterministic CombatEngine encounter and Strike resolution]
  - phase: 04-graph-runtime-and-agent-skills
    provides: [SagaGraphState, StateGraph routing, AgentServices, TUI graph runtime wiring]
provides:
  - RulesLawyer first-slice command parser for deterministic checks, combat setup, Strikes, movement, and turn ending
  - Combat phase routing into RulesLawyer instead of END
  - TUI play-state sheet seeding with preservation of existing character state
affects: [phase-05-tui-sheet-and-dice, phase-05-vertical-slice-qa, phase-06-ai-gm-story-loop]

tech-stack:
  added: []
  patterns: [exact anchored regex command parsing, deterministic mechanics service construction inside graph node, fail-closed rules error narration, graph play-state sheet preservation]

key-files:
  created:
    - tests/agents/test_rules_lawyer_phase5.py
  modified:
    - src/sagasmith/agents/rules_lawyer/node.py
    - src/sagasmith/graph/routing.py
    - src/sagasmith/graph/graph.py
    - src/sagasmith/tui/app.py
    - tests/agents/test_node_contracts.py
    - tests/graph/test_routing.py
    - tests/graph/test_graph_bootstrap.py

key-decisions:
  - "RulesLawyer accepts only anchored first-slice command forms and returns deterministic `Rules error:` narration for unsupported input rather than silent `{}`."
  - "Combat phase now routes to RulesLawyer and the compiled graph includes `rules_lawyer` as a START branch destination."
  - "TUI play-state construction seeds the first-slice pregen only when no sheet exists, preserving live HP/combat mutations."

patterns-established:
  - "Rules node command parsing normalizes whitespace/case but rejects unsupported stats, targets, and position tags before rolling."
  - "Combat Strike damage roll IDs are surfaced in pending narration until a dedicated damage result schema is introduced."

requirements-completed: [RULE-05, RULE-06, RULE-07, RULE-08, RULE-09, RULE-10, RULE-11, RULE-12]

duration: 5 min
completed: 2026-04-28
---

# Phase 5 Plan 3: RulesLawyer Graph Wiring and Combat Routing Summary

**Deterministic RulesLawyer graph wiring for first-slice checks and combat commands, with combat phase routing and TUI pregen sheet seeding.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-28T11:16:55Z
- **Completed:** 2026-04-28T11:21:52Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Replaced RulesLawyer trigger phrases with exact, case-insensitive first-slice command parsing for checks, combat start, Strikes, movement, and turn ending.
- Wired RulesLawyer to `RulesEngine(dice=services.dice)` and `CombatEngine(dice=services.dice, rules=rules_engine)` with no `services.llm` access.
- Added deterministic fail-closed error narration for unsupported input, parser mismatch, and `ValueError` from rules/combat services without adding rolls.
- Routed `phase="combat"` to `rules_lawyer` and added the compiled StateGraph branch destination required for runtime execution.
- Updated TUI play-state construction to seed `make_first_slice_character().model_dump()` only when an existing sheet is absent.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: RulesLawyer mechanics tests** - `944a62c` (test)
2. **Task 1 GREEN: RulesLawyer deterministic mechanics implementation** - `79439a2` (feat)
3. **Task 2 RED: Combat routing and play-state tests** - `1a5bf09` (test)
4. **Task 2 GREEN: Combat routing and TUI sheet seeding** - `f7b6b2a` (feat)
5. **Task 2 verification fix: compiled graph branch target** - `fdfb331` (fix)

**Plan metadata:** pending final docs commit

_Note: This TDD plan produced RED and GREEN commits for both tasks, plus one Rule 3 verification fix commit for the compiled graph branch mapping._

## Files Created/Modified

- `tests/agents/test_rules_lawyer_phase5.py` - New Phase 5 behavior tests for deterministic check parsing, combat setup, Strikes, invalid action errors, no LLM access, combat completion, and TUI sheet seeding.
- `src/sagasmith/agents/rules_lawyer/node.py` - Replaces trigger phrases with first-slice parser and deterministic RulesEngine/CombatEngine execution.
- `src/sagasmith/graph/routing.py` - Routes combat phase to `rules_lawyer`.
- `src/sagasmith/graph/graph.py` - Adds `rules_lawyer` as a START conditional-edge destination.
- `src/sagasmith/tui/app.py` - Seeds first-slice pregen sheet while preserving an existing sheet.
- `tests/agents/test_node_contracts.py` - Updates node contract expectations for new deterministic RulesLawyer command/error behavior.
- `tests/graph/test_routing.py` - Covers combat routing and mechanics state fields in `SagaGraphState`.
- `tests/graph/test_graph_bootstrap.py` - Updates compiled graph coverage for combat routing through RulesLawyer.

## Decisions Made

- Kept RulesLawyer parsing narrow and explicit with anchored regexes rather than permissive prose extraction to prevent hidden or LLM-authored mechanics.
- Returned user-visible `Rules error:` narration for unsupported input instead of `{}` so invalid first-slice actions are deterministic and visible to the TUI.
- Preserved existing character sheets in TUI-built play state so later combat HP mutations are not overwritten by the first-slice pregen factory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added compiled graph branch mapping for combat routing**
- **Found during:** Task 2 verification
- **Issue:** Changing `PHASE_TO_ENTRY[Phase.COMBAT.value]` to `"rules_lawyer"` made `route_by_phase` correct, but the compiled StateGraph START conditional edge map did not include `"rules_lawyer"`, producing a runtime `KeyError` in graph bootstrap tests.
- **Fix:** Added `"rules_lawyer": "rules_lawyer"` to `src/sagasmith/graph/graph.py` and updated `tests/graph/test_graph_bootstrap.py` to prove combat now routes through RulesLawyer, Orator, and Archivist.
- **Files modified:** `src/sagasmith/graph/graph.py`, `tests/graph/test_graph_bootstrap.py`
- **Verification:** `uv run pytest tests/graph/test_graph_bootstrap.py tests/agents/test_node_contracts.py -q` — PASS (23 passed); plan pytest and pyright also pass.
- **Committed in:** `fdfb331`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required for the planned combat route to execute in the compiled graph. No scope creep beyond graph routing correctness.

## Issues Encountered

- `gsd-sdk query` is unavailable in this environment (`gsd-sdk` only exposes `run`, `auto`, and `init`), so tracking artifacts were updated manually while preserving execute-plan semantics.

## TDD Gate Compliance

- Task 1 RED commit `944a62c` preceded GREEN commit `79439a2`.
- Task 2 RED commit `1a5bf09` preceded GREEN commit `f7b6b2a`.
- Verification fix commit `fdfb331` followed GREEN after graph bootstrap exposed the missing branch target.

## Known Stubs

None.

## Verification Results

- `uv run pytest tests/agents/test_rules_lawyer_phase5.py -q` — PASS (8 passed after Task 1)
- `uv run pytest tests/graph/test_routing.py tests/agents/test_rules_lawyer_phase5.py -q` — PASS (22 passed)
- `uv run pytest tests/agents/test_rules_lawyer_phase5.py tests/graph/test_routing.py -q` — PASS (22 passed)
- `uv run pytest tests/graph/test_graph_bootstrap.py tests/agents/test_node_contracts.py -q` — PASS (23 passed)
- `uv run pyright src/sagasmith/agents/rules_lawyer src/sagasmith/graph src/sagasmith/tui/app.py tests/agents tests/graph` — PASS (0 errors, existing LangGraph/test typing warnings only)

## Acceptance Criteria Verification

- Task 1: `RulesEngine(` and `CombatEngine(` are present; `_TRIGGER_PHRASES` was removed; tests cover unsupported input error narration, whitespace/case-normalized checks, caught combat `ValueError`, no LLM access, and PC target rejection without new rolls.
- Task 2: `Phase.COMBAT.value: "rules_lawyer"` is present; TUI play state seeds `make_first_slice_character().model_dump()` and preserves an existing `character_sheet`; graph tests assert combat routes to `rules_lawyer`; RulesLawyer tests assert completed combat returns `phase == "play"`.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the plan threat model covered player input parsing, graph state mutation, and LLM access prevention.

## Next Phase Readiness

Ready for `05-04`: graph play/combat inputs now reach deterministic first-slice mechanics with valid pregen sheet data, visible deterministic errors, and combat routing through RulesLawyer.

## Self-Check: PASSED

- Verified created file exists: `tests/agents/test_rules_lawyer_phase5.py` and this summary.
- Verified task commits exist: `944a62c`, `79439a2`, `1a5bf09`, `f7b6b2a`, `fdfb331`.
- Verified final plan pytest and pyright checks pass.

---
*Phase: 05-rules-first-pf2e-vertical-slice*
*Completed: 2026-04-28*
