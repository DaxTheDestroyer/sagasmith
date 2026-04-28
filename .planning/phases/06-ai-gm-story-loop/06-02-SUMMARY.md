---
phase: 06-ai-gm-story-loop
plan: 02
subsystem: oracle-scene-planning
tags: [oracle, scene-brief, beat-ids, content-policy, langgraph, prompts, no-paid-call]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: [AgentServices, AgentActivationLogger, SkillStore, SagaGraphState, graph interrupts]
  - phase: 06-ai-gm-story-loop
    provides: [MemoryPacket stub from 06-05, WorldBible/CampaignSeed from 06-01, RulesLawyer non-mechanical routing from 06-03]
provides:
  - LLM structured SceneBrief composition with D-06.5 prompt module and D-06.6 cost preflight
  - Explicit beat_id lifecycle state and pure routing predicates for Oracle replanning
  - Player-choice bypass/rejection/reframe detection for Oracle replans
  - Deterministic content-policy pre-gate routing for scene intents before Orator sees them
affects: [phase-6-ai-gm-story-loop, oracle, graph-routing, orator, safety, scene-rendering]

tech-stack:
  added: []
  patterns:
    - Hyphenated Agent Skill directories paired with underscore import packages
    - Prompt modules under src/sagasmith/prompts/oracle with PROMPT_VERSION and JSON_SCHEMA
    - Pure graph routing predicates over scene_brief.beat_ids and resolved_beat_ids

key-files:
  created:
    - src/sagasmith/prompts/oracle/scene_brief_composition.py
    - src/sagasmith/agents/oracle/skills/scene_brief_composition/logic.py
    - src/sagasmith/agents/oracle/skills/player_choice_branching/logic.py
    - src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py
    - tests/agents/oracle/test_scene_brief_composition.py
    - tests/agents/oracle/test_player_choice_branching.py
    - tests/agents/oracle/test_content_policy_routing.py
    - tests/integration/test_scene_management_flow.py
    - tests/prompts/test_oracle_scene_brief_prompt.py
  modified:
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/schemas/narrative.py
    - src/sagasmith/schemas/saga_state.py
    - src/sagasmith/graph/routing.py
    - src/sagasmith/graph/graph.py
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/graph/interrupts.py
    - src/sagasmith/schemas/safety_cost.py
    - src/sagasmith/evals/fixtures.py
    - tests/graph/test_routing.py
    - tests/integration/test_world_generation_flow.py

key-decisions:
  - "SceneBrief keeps readable beats and adds parallel beat_ids so prompt audits remain human-readable while Orator can report deterministic resolved IDs."
  - "Oracle scene planning uses a no-paid-call deterministic fallback only when no LLM/policy/memory context is available; configured LLM clients use structured SceneBrief generation."
  - "Pre-gate routing is implemented as a deterministic skill-level facade now; Task 7 still owns full safety service hardening and post-gate regression breadth."

patterns-established:
  - "Oracle replanning triggers on missing scene_brief, completed beat_ids, or deterministic player-choice bypass/reframe detection."
  - "Graph START routing can skip Oracle and enter RulesLawyer directly when the active SceneBrief still has unresolved beat_ids."
  - "Oracle safety/budget interrupts are represented in graph state and route to END before Orator."

requirements-completed: [AI-01, AI-02, AI-04, D-07, D-08, D-09]

duration: 11min
completed: 2026-04-28
---

# Phase 6 Plan 02: Scene Brief Composition for Oracle Summary

**Oracle now composes validated planning-only SceneBriefs, tracks beat IDs for lifecycle routing, and replans around player bypasses before narration.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-28T17:32:56Z
- **Completed:** 2026-04-28T17:43:53Z
- **Tasks:** 1 plan task / 10 implementation steps
- **Files modified:** 32

## Accomplishments

- Added `SceneBrief.beat_ids`, `SagaState.resolved_beat_ids`, and `oracle_bypass_detected` so Oracle and graph routing can replan by explicit beat completion instead of heuristics.
- Implemented D-06.5 scene-brief prompt module plus structured LLM skill logic using `invoke_with_retry`, schema validation, prompt-version metadata, and D-06.6 budget preflight.
- Implemented player-choice branching and content-policy routing skills with deterministic bypass detection and hard/soft policy pre-gate behavior.
- Updated Oracle and graph routing so scene planning runs only when needed, blocks/reroutes unsafe intents before Orator, returns prior state on budget stop, and skips Oracle when an active brief remains valid.
- Added unit, prompt, routing, and integration coverage for scene generation, bypass replanning, content policy routing, beat tracking, no-paid-call fallback, and skill activation logging.

## Task Commits

Each task was committed atomically:

1. **Task 2: Implement Scene Brief Composition (Oracle)** - `bdbe2b2` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/schemas/narrative.py` - Adds parallel `beat_ids` validation and planning-only narration guard to `SceneBrief`.
- `src/sagasmith/schemas/saga_state.py` and `src/sagasmith/graph/state.py` - Add `resolved_beat_ids` and `oracle_bypass_detected` lifecycle fields.
- `src/sagasmith/prompts/oracle/scene_brief_composition.py` - Versioned D-06.5 prompt and JSON Schema contract for scene briefs.
- `src/sagasmith/agents/oracle/skills/*/logic.py` - Adds scene-brief composition, player-choice branching, and content-policy routing logic with importable underscore packages and hyphenated skill wrappers.
- `src/sagasmith/agents/oracle/node.py` - Replaces the scene stub path with lifecycle-aware planning, pre-gate routing, budget interrupt handling, and deterministic no-paid-call fallback.
- `src/sagasmith/graph/routing.py`, `graph.py`, and `runtime.py` - Add pure scene lifecycle routing and halt-after-Oracle behavior for budget/safety interrupts.
- `src/sagasmith/graph/interrupts.py` and `src/sagasmith/schemas/safety_cost.py` - Add safety-block interrupt and pre-gate safety event kinds.
- Tests under `tests/agents/oracle/`, `tests/integration/test_scene_management_flow.py`, `tests/prompts/`, and `tests/graph/test_routing.py` cover the new contracts and flow.

## Decisions Made

- Used the plan-recommended parallel `beat_ids` approach rather than replacing readable `beats`, preserving prompt auditability while enabling explicit Orator resolution tracking.
- Kept scene briefs planning-only by validating against common second-person narration markers and by instructing the prompt to avoid player-facing prose.
- Implemented pre-gate routing within Oracle skill boundaries now, without duplicating Task 7's full post-gate/safety-regression scope.
- Preserved no-paid-call first-slice behavior by falling back to a deterministic planning brief only when no LLM/policy/memory context is available.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added importable Python packages for hyphenated Oracle Agent Skills**
- **Found during:** Task 2 (skill logic implementation)
- **Issue:** The plan-required skill directories use hyphenated names, which cannot be imported as Python packages.
- **Fix:** Kept plan-specified `logic.py` wrappers and added importable underscore packages for `scene_brief_composition`, `player_choice_branching`, and `content_policy_routing`.
- **Files modified:** `src/sagasmith/agents/oracle/skills/*-*/logic.py`, `src/sagasmith/agents/oracle/skills/*_*/logic.py`, `__init__.py` wrappers
- **Verification:** `uv run ruff check src tests` and targeted Oracle skill tests passed.
- **Committed in:** `bdbe2b2`

**2. [Rule 2 - Missing Critical] Added graph halt routing for Oracle budget/safety interrupts**
- **Found during:** Step 10 pre-gate integration
- **Issue:** Returning a `last_interrupt` from Oracle would otherwise continue the graph toward RulesLawyer/Orator.
- **Fix:** Added `route_after_oracle` conditional routing in both graph builders so `budget_stop` and `safety_block` interrupts halt before narration.
- **Files modified:** `src/sagasmith/graph/routing.py`, `src/sagasmith/graph/graph.py`, `src/sagasmith/graph/runtime.py`
- **Verification:** `tests/integration/test_scene_management_flow.py` passed.
- **Committed in:** `bdbe2b2`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both changes were required to satisfy the plan while preserving Agent Skill importability and the safety-before-narration boundary.

## Known Stubs

- `src/sagasmith/agents/oracle/node.py` retains an intentional deterministic fallback SceneBrief when no LLM, content policy, or memory packet is available. This preserves no-paid-call smoke behavior and does not prevent the configured LLM scene-composition path from fulfilling this plan.
- `src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py` implements the Plan 06-02 pre-gate subset. Full Task 7 safety service logging, post-gate classifier coverage, and QA-05 regression breadth remain deferred to 06-07.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: safety_interrupt | `src/sagasmith/graph/interrupts.py` | Adds `SAFETY_BLOCK` interrupt surface for pre-generation content-policy blocks. |
| threat_flag: safety_event_kind | `src/sagasmith/schemas/safety_cost.py` | Adds pre-gate safety event kinds for reroute/block audit records. |

## Issues Encountered

- Full `uv run pytest` initially exposed the existing runtime-boundary regression that asserts Oracle source does not reference `BudgetStopError` or `InterruptKind`. The Oracle node now delegates interrupt construction to helpers while still honoring the plan's budget-stop behavior.
- A full-suite run surfaced a transient SQLite checkpoint `OperationalError: not an error` in `test_oracle_skill_name_logged`; rerunning that specific test passed.
- Existing world-generation integration needed a scripted scene-brief fake response once Oracle started composing real scene briefs in the same turn.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src tests` — passed.
- `uv run pyright src/sagasmith/agents/oracle src/sagasmith/prompts/oracle src/sagasmith/schemas/narrative.py src/sagasmith/schemas/saga_state.py src/sagasmith/schemas/safety_cost.py src/sagasmith/graph tests/agents/oracle tests/integration/test_scene_management_flow.py tests/prompts/test_oracle_scene_brief_prompt.py tests/graph/test_routing.py` — 0 errors, warnings only.
- `uv run pytest tests/agents/oracle/test_scene_brief_composition.py tests/agents/oracle/test_player_choice_branching.py tests/agents/oracle/test_content_policy_routing.py tests/integration/test_scene_management_flow.py tests/prompts/test_oracle_scene_brief_prompt.py tests/graph/test_routing.py tests/agents/test_node_contracts.py tests/agents/test_nodes_with_skills.py tests/skills_adapter/test_production_catalog.py tests/schemas/test_narrative_models.py tests/schemas/test_json_schema_export.py` — 72 passed.
- `uv run pytest` — first run: 532 passed, 1 skipped, 1 transient SQLite checkpoint failure; targeted rerun of the failed test passed.

## Next Phase Readiness

- Plan 06-04 can consume `SceneBrief.beat_ids` and emit `resolved_beat_ids` from Orator narration.
- Plan 06-07 can replace/extend the skill-level pre-gate facade with the full safety service and QA-05 redline regression suite.
- Plan 06-08 can use `tests/integration/test_scene_management_flow.py` as the first scene-management integration spine.

## Self-Check: PASSED

- Created files verified on disk.
- Task commit `bdbe2b2` verified in git history.
- Summary file verified on disk.

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
