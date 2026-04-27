---
phase: 04-graph-runtime-and-agent-skills
plan: 05
subsystem: graph-runtime
tags: [langgraph, agent-skills, skillstore, contextvar, activation-log, pydantic]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: "Persistent graph runtime (GraphRuntime, activation logging, checkpointing) from 04-02"
  - phase: 04-graph-runtime-and-agent-skills
    provides: "Skills adapter (SkillStore, load_skill, frontmatter validation) from 04-04"

provides:
  - 14 production SKILL.md files (13 first_slice=true + 1 first_slice=false)
  - _default_skill_store() bootstrap helper with loud error-on-scan-failure
  - Per-node set_skill wiring via get_current_activation() contextvar handoff
  - rules_lawyer load_skill + set_skill on trigger match
  - Graceful degradation when activation logger or skill_store is absent
  - End-to-end first_slice_only=True play turn test

affects:
  - phase-05-rules-first-pf2e-vertical-slice
  - phase-06-ai-gm-story-loop
  - phase-07-memory-vault-resume

tech-stack:
  added: []
  patterns:
    - "ContextVar handoff: nodes call get_current_activation().set_skill(...) without re-plumbing"
    - "Defensive node pattern: if activation is not None and store.find(...) is not None"
    - "Lazy bootstrap: _default_skill_store() only runs on GraphBootstrap.from_services, not import"

key-files:
  created:
    - src/sagasmith/skills/schema-validation/SKILL.md
    - src/sagasmith/skills/safety-redline-check/SKILL.md
    - src/sagasmith/skills/command-dispatch/SKILL.md
    - src/sagasmith/agents/oracle/skills/scene-brief-composition/SKILL.md
    - src/sagasmith/agents/oracle/skills/player-choice-branching/SKILL.md
    - src/sagasmith/agents/oracle/skills/content-policy-routing/SKILL.md
    - src/sagasmith/agents/oracle/skills/inline-npc-creation/SKILL.md
    - src/sagasmith/agents/rules_lawyer/skills/degree-of-success/SKILL.md
    - src/sagasmith/agents/rules_lawyer/skills/seeded-roll-resolution/SKILL.md
    - src/sagasmith/agents/rules_lawyer/skills/skill-check-resolution/SKILL.md
    - src/sagasmith/agents/orator/skills/scene-rendering/SKILL.md
    - src/sagasmith/agents/archivist/skills/memory-packet-assembly/SKILL.md
    - src/sagasmith/agents/archivist/skills/turn-close-persistence/SKILL.md
    - src/sagasmith/agents/onboarding/skills/onboarding-phase-wizard/SKILL.md
    - tests/skills_adapter/test_production_catalog.py
    - tests/agents/test_nodes_with_skills.py
  modified:
    - src/sagasmith/graph/bootstrap.py
    - src/sagasmith/graph/__init__.py
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/agents/rules_lawyer/node.py
    - src/sagasmith/agents/orator/node.py
    - src/sagasmith/agents/archivist/node.py
    - src/sagasmith/agents/onboarding/node.py
    - tests/graph/test_checkpoints.py

key-decisions:
  - "Lazy skill_store construction: _default_skill_store() runs on GraphBootstrap.from_services, NOT at module import, so test fixtures remain cheap"
  - "Required-set containment tests instead of exact counts per Codex review feedback"
  - "memory-packet-assembly marked first_slice=false with explicit Phase 7 ownership in SKILL.md body"
  - "rules_lawyer_node imports load_skill at module level (not inline) to satisfy ruff I001"

patterns-established:
  - "Defensive set_skill: if activation is not None and store.find(name, scope) is not None"
  - "ContextVar handoff for Phase 6: LLM-driven nodes will wrap their LLM calls with set_skill"
  - "Bootstrap loud-on-error: SkillValidationError at startup prevents silent skill degradation"

requirements-completed: [SKILL-04, SKILL-05]

duration: 10min
completed: 2026-04-27T15:27:13Z
---

# Phase 04 Plan 05: First-Slice Agent Skills Catalog + Node Wiring Summary

**Shipped 14 production SKILL.md files across 5 agents + 3 cross-cutting skills, wired every agent node to record its active skill via the contextvar handoff from Plan 04-02, and proved an end-to-end play turn with `first_slice_only=True` completes.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-27T15:17:17Z
- **Completed:** 2026-04-27T15:27:13Z
- **Tasks:** 2
- **Files modified:** 24

## Accomplishments
- 14 SKILL.md files with valid frontmatter, deterministic handler references, and spec-aligned implementation_surface
- `_default_skill_store()` bootstrap helper that scans production roots and raises `SkillValidationError` on errors
- Per-node `set_skill` wiring for oracle, rules_lawyer, orator, archivist, and onboarding
- `rules_lawyer_node` calls `load_skill` for `skill-check-resolution` on trigger match
- Graceful degradation when nodes run outside activation-logger or skill-store context
- End-to-end `first_slice_only=True` play turn test proving correct skill_names in agent_skill_log

## Task Commits

1. **Task 1: Ship 14 first-slice SKILL.md files + bootstrap helper** - `7f24732` (feat)
2. **Task 2: Wire set_skill calls into every agent node via contextvar handoff** - `ab6b5bd` (feat)

## Files Created/Modified
- `src/sagasmith/skills/__init__.py` - Resource root for importlib.resources
- `src/sagasmith/skills/*/SKILL.md` - 3 cross-cutting skills (schema-validation, safety-redline-check, command-dispatch)
- `src/sagasmith/agents/oracle/skills/*/SKILL.md` - 4 Oracle skills
- `src/sagasmith/agents/rules_lawyer/skills/*/SKILL.md` - 3 deterministic RulesLawyer skills
- `src/sagasmith/agents/orator/skills/scene-rendering/SKILL.md` - Orator rendering skill
- `src/sagasmith/agents/archivist/skills/*/SKILL.md` - 2 Archivist skills (turn-close-persistence first_slice=true, memory-packet-assembly first_slice=false)
- `src/sagasmith/agents/onboarding/skills/onboarding-phase-wizard/SKILL.md` - Onboarding wizard skill
- `src/sagasmith/graph/bootstrap.py` - `_default_skill_store()`, `skill_store` on `AgentServices`
- `src/sagasmith/graph/__init__.py` - Re-export `_default_skill_store`
- `src/sagasmith/agents/*/node.py` - `set_skill` wiring in all 5 agent nodes
- `tests/skills_adapter/test_production_catalog.py` - 8 tests for production catalog
- `tests/agents/test_nodes_with_skills.py` - 12 tests for node skill wiring
- `tests/graph/test_checkpoints.py` - Updated activation_logging_counts to assert skill_names

## Decisions Made
- Lazy skill_store construction: `_default_skill_store()` only runs on `GraphBootstrap.from_services`, not at module import, preserving cheap test fixture imports
- Required-set containment tests instead of exact counts per Codex review feedback
- `memory-packet-assembly` marked `first_slice: false` with explicit Phase 7 ownership in its SKILL.md body
- `rules_lawyer_node` imports `load_skill` at module level (not inline) to satisfy ruff I001

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_activation_logging_counts to assert populated skill_names**
- **Found during:** Task 2 verification
- **Issue:** Existing test `test_activation_logging_counts` asserted `skill_name is None` for all rows, but Task 2 intentionally wires `set_skill` calls so skill_names are now populated
- **Fix:** Updated the test to assert the expected skill_names per agent instead of NULL
- **Files modified:** `tests/graph/test_checkpoints.py`
- **Verification:** Full test suite passes (442 passed)
- **Committed in:** `ab6b5bd` (Task 2 commit)

**2. [Rule 3 - Blocking] Fixed ruff I001 import ordering in rules_lawyer/node.py**
- **Found during:** Task 2 verification
- **Issue:** Inline imports inside `try` block triggered ruff I001 (unsorted imports)
- **Fix:** Moved `load_skill` and error imports to module top-level
- **Files modified:** `src/sagasmith/agents/rules_lawyer/node.py`
- **Verification:** `uv run ruff check` clean
- **Committed in:** `ab6b5bd` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness and tooling compliance. No scope creep.

## Issues Encountered
- None beyond the expected test update when enabling skill_name population

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 5 (Rules-First PF2e Vertical Slice) can build on the deterministic RulesLawyer skills
- Phase 6 (AI GM Story Loop) can use the contextvar handoff pattern to wrap LLM calls with `set_skill`
- Phase 7 (Memory, Vault, and Resume) owns `memory-packet-assembly` implementation

## Deferred Skills (with target phases)
| Skill | Agent | Target Phase |
|-------|-------|-------------|
| encounter-budget-validation | rules_lawyer | Phase 5 |
| strike-resolution | rules_lawyer | Phase 5 |
| initiative-resolution | rules_lawyer | Phase 5 |
| action-economy-tracking | rules_lawyer | Phase 5 |
| theater-positioning | rules_lawyer | Phase 5 |
| condition-application | rules_lawyer | Phase 5 |
| retcon-aware-replay | rules_lawyer | Phase 8 |
| world-bible-generation | oracle | Phase 6 |
| campaign-seed-generation | oracle | Phase 6 |
| callback-seeding | oracle | Phase 6 |
| callback-payoff-selection | oracle | Phase 6 |
| encounter-request-composition | oracle | Phase 5 |
| pacing-calibration | oracle | Phase 6 |
| canon-conflict-response | oracle | Phase 6 |
| memory-packet-assembly | archivist | Phase 7 (first_slice=false, stub shipped) |
| callback-reachability-query | archivist | Phase 7 |
| entity-resolution | archivist | Phase 7 |
| vault-page-upsert | archivist | Phase 7 |
| visibility-promotion | archivist | Phase 7 |
| canon-conflict-detection | archivist | Phase 7 |
| rolling-summary-update | archivist | Phase 7 |
| session-page-authoring | archivist | Phase 7 |
| player-vault-sync | archivist | Phase 7 |
| master-vault-unlock | archivist | Phase 8 |

## Self-Check: PASSED
- All created files exist on disk
- Commits `7f24732` and `ab6b5bd` verified in git log
- Full test suite: 442 passed, 0 failed
- SkillStore scan returns 0 errors
- Required-set coverage test passes
- End-to-end first_slice_only play turn passes

---
*Phase: 04-graph-runtime-and-agent-skills*
*Completed: 2026-04-27*
