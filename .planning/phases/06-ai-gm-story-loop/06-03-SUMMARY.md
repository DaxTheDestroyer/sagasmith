---
phase: 06-ai-gm-story-loop
plan: 03
subsystem: rules-lawyer-intent
tags: [rules-lawyer, intent-resolution, check-proposal, agent-skills, no-paid-call]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: [AgentServices, AgentActivationLogger, SkillStore, graph nodes]
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [RulesEngine, CombatEngine, first-slice RulesLawyer command routing]
provides:
  - Hybrid deterministic-first intent resolution service for RulesLawyer
  - Intent-to-CheckProposal conversion that rebuilds modifiers and DCs from deterministic services
  - RulesLawyer node natural-language routing with non-mechanical skip behavior
  - Skill definitions for skill-check-resolution and combat-resolution hybrid surfaces
affects: [phase-6-ai-gm-story-loop, rules-lawyer, deterministic-rules-boundary, agent-skills]

tech-stack:
  added: []
  patterns:
    - Deterministic regex/natural-language patterns before optional LLM classification fallback
    - LLM intent output treated as action-shape classification only, never math
    - Proposal validation through CheckProposal before deterministic service resolution

key-files:
  created:
    - src/sagasmith/services/intent_resolution.py
    - src/sagasmith/agents/rules_lawyer/intent_to_proposal.py
    - src/sagasmith/prompts/rules_lawyer/__init__.py
    - src/sagasmith/prompts/rules_lawyer/intent_resolution.py
    - src/sagasmith/agents/rules_lawyer/skills/combat-resolution/SKILL.md
    - tests/services/test_intent_resolution.py
    - tests/agents/rules_lawyer/test_intent_to_proposal.py
    - tests/integration/test_intent_resolution_flow.py
  modified:
    - src/sagasmith/agents/rules_lawyer/node.py
    - src/sagasmith/services/rules_engine.py
    - src/sagasmith/agents/rules_lawyer/skills/skill-check-resolution/SKILL.md
    - tests/agents/test_node_contracts.py
    - tests/skills_adapter/test_production_catalog.py

key-decisions:
  - "RulesLawyer LLM fallback classifies only action shape; CheckProposal math is rebuilt from CharacterSheet, CombatState, RulesEngine, and CombatEngine."
  - "Non-mechanical player input now returns no mechanics update so narration can proceed without a visible rules error."
  - "Missing or exhausted intent LLM fallback degrades to deterministic-only routing rather than failing the turn."

patterns-established:
  - "IntentCandidate is the untrusted classification boundary; CheckProposal is the deterministic validation boundary."
  - "Agent Skill metadata marks RulesLawyer proposal-facing skills as hybrid while preserving deterministic execution ownership."

requirements-completed: [AI-06, D-16, D-17]

duration: 7min
completed: 2026-04-28
---

# Phase 6 Plan 03: Intent-to-Proposal Layer for RulesLawyer Summary

**RulesLawyer now converts explicit and natural-language player intent into schema-validated mechanical proposals while deterministic services remain the only source of rules math.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-28T17:22:30Z
- **Completed:** 2026-04-28T17:29:40Z
- **Tasks:** 1 plan task / 6 implementation steps
- **Files modified:** 13

## Accomplishments

- Implemented `intent_resolution` with deterministic explicit command patterns, common natural-language PF2e action cues, optional structured LLM fallback, confidence scoring, and budget-stop degradation.
- Added `intent_to_proposal` conversion that validates `CheckProposal` values and derives modifiers/DCs from `RulesEngine`, `CombatEngine`, `CharacterSheet`, and `CombatState` rather than LLM output.
- Updated RulesLawyer node routing so natural-language skill actions resolve, unsupported mechanical commands still produce visible rules errors, and non-mechanical input skips mechanics for narration.
- Added/updated RulesLawyer Agent Skill definitions and catalog tests for hybrid skill-check and combat resolution.
- Added unit and integration coverage for explicit patterns, natural-language conversion, LLM fallback, budget fallback, proposal validation, graph skill logging, and no-paid-call behavior.

## Task Commits

Each task was committed atomically:

1. **Task 3: Implement Intent-to-Proposal Layer (RulesLawyer)** - `7e8bc58` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/services/intent_resolution.py` - Hybrid deterministic-first intent resolver with `IntentCandidate`, confidence ranking, LLM fallback, and budget fallback.
- `src/sagasmith/agents/rules_lawyer/intent_to_proposal.py` - Converts classified intents to deterministic, schema-validated `CheckProposal` values.
- `src/sagasmith/prompts/rules_lawyer/intent_resolution.py` - Versioned structured prompt/schema for RulesLawyer intent classification fallback.
- `src/sagasmith/agents/rules_lawyer/node.py` - Wires intent resolution into skill/check/combat routing while preserving deterministic resolution.
- `src/sagasmith/services/rules_engine.py` - Allows proposal IDs to use the caller's roll index when building non-rolling proposals.
- `src/sagasmith/agents/rules_lawyer/skills/skill-check-resolution/SKILL.md` - Updates the skill contract to hybrid intent-to-proposal plus deterministic resolution.
- `src/sagasmith/agents/rules_lawyer/skills/combat-resolution/SKILL.md` - Adds combat resolution skill definition for attack/move/turn/encounter intent handling.
- Tests under `tests/services/`, `tests/agents/rules_lawyer/`, and `tests/integration/` cover intent classification, proposal conversion, and graph flow logging.
- Existing node-contract and production-catalog tests updated for non-mechanical skip behavior and hybrid RulesLawyer skill metadata.

## Decisions Made

- LLM fallback is intentionally classification-only: it can suggest supported action/stat/target shape, but all DCs, modifiers, attack AC, damage, action counts, HP deltas, and degree outcomes are recomputed by deterministic services.
- Non-mechanical player input returns `{}` from RulesLawyer so the graph can proceed to narration instead of showing a rules error for ordinary roleplay text.
- If the LLM fallback is unavailable, unscripted in deterministic tests, or blocked by budget, RulesLawyer falls back to deterministic-only routing; budget exhaustion surfaces a concise hint to use explicit `/check athletics 15` syntax.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added deterministic degradation when intent LLM fallback is unavailable**
- **Found during:** Task 3 (full-suite integration verification)
- **Issue:** Existing no-paid-call/world-generation flows can inject an LLM client for Oracle without scripting RulesLawyer intent fallback. Letting an unscripted fallback error bubble up would fail unrelated turns.
- **Fix:** `resolve_intents` now returns no candidates on fallback provider failure, preserving deterministic-only routing unless a deterministic pattern matches.
- **Files modified:** `src/sagasmith/services/intent_resolution.py`
- **Verification:** `uv run pytest tests/integration/test_world_generation_flow.py` passed; full `uv run pytest` subsequently had only a known transient checkpoint assertion that passed on rerun.
- **Committed in:** `7e8bc58`

**2. [Rule 2 - Missing Critical] Updated production skill catalog expectations for hybrid RulesLawyer skills**
- **Found during:** Task 5/6 skill verification
- **Issue:** Adding `combat-resolution` and changing `skill-check-resolution` to hybrid caused the production catalog contract test to reject the new shipped skill metadata.
- **Fix:** Added `combat-resolution` to required RulesLawyer skills and updated expected implementation surfaces for both proposal-facing RulesLawyer skills.
- **Files modified:** `tests/skills_adapter/test_production_catalog.py`
- **Verification:** `uv run pytest tests/skills_adapter/test_production_catalog.py tests/agents/test_nodes_with_skills.py` passed.
- **Committed in:** `7e8bc58`

---

**Total deviations:** 2 auto-fixed (2 missing critical)
**Impact on plan:** Both changes were necessary to keep no-paid-call flows deterministic and skill catalog validation aligned with the new hybrid RulesLawyer scope.

## Known Stubs

None - this plan's intent resolution/proposal layer is wired for first-slice skill and combat actions. Broader PF2e actions remain outside the first-slice rules scope rather than stubs.

## Issues Encountered

- Full `uv run pytest` initially surfaced an existing transient SQLite/LangGraph checkpoint assertion in `test_resume_and_close_writes_final_checkpoint_and_completes_turn`; rerunning that specific test passed.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/services/test_intent_resolution.py tests/agents/rules_lawyer/test_intent_to_proposal.py tests/integration/test_intent_resolution_flow.py tests/agents/test_rules_lawyer_phase5.py` — passed.
- `uv run pytest tests/skills_adapter/test_production_catalog.py tests/agents/test_nodes_with_skills.py` — passed.
- `uv run ruff check src tests` — passed.
- `uv run pyright src/sagasmith/services/intent_resolution.py src/sagasmith/agents/rules_lawyer src/sagasmith/prompts/rules_lawyer tests/services/test_intent_resolution.py tests/agents/rules_lawyer/test_intent_to_proposal.py tests/integration/test_intent_resolution_flow.py tests/agents/test_node_contracts.py tests/skills_adapter/test_production_catalog.py` — 0 errors, warnings only.
- `uv run pytest` — 516 passed, 1 skipped, 1 transient failure; rerun of `tests/graph/test_checkpoints.py::test_resume_and_close_writes_final_checkpoint_and_completes_turn` passed.

## Next Phase Readiness

- Plan 06-02/06-04 can rely on RulesLawyer returning no mechanics update for non-mechanical roleplay input and deterministic `CheckResult` entries for recognized first-slice mechanical intent.
- Later Phase 6 work can add richer scene-context DC hints, but this plan already protects the trust boundary by ignoring LLM-authored math.

## Self-Check: PASSED

- Created files verified on disk.
- Task commit `7e8bc58` verified in git history.
- Summary file verified on disk.

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
