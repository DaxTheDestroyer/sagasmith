---
phase: 06-ai-gm-story-loop
plan: 01
subsystem: oracle-worldgen
tags: [oracle, world-bible, campaign-seed, pydantic, prompts, no-paid-call]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: [AgentServices, AgentActivationLogger, SkillStore, SagaGraphState]
  - phase: 06-ai-gm-story-loop
    provides: [transcript-only MemoryPacket context from 06-05]
provides:
  - WorldBible and CampaignSeed Pydantic schemas exported as LLM-boundary JSON Schema
  - Versioned Oracle prompt modules for world-bible-generation and campaign-seed-generation
  - Oracle Agent Skill packages and importable skill logic for one-shot campaign context generation
  - Idempotent Oracle node worldgen integration with deterministic fake-client tests
affects: [phase-6-ai-gm-story-loop, oracle, graph-state, schema-export, prompt-testing]

tech-stack:
  added: []
  patterns:
    - Versioned prompt modules under src/sagasmith/prompts/oracle per D-06.5
    - Hyphenated Agent Skill directories paired with underscore import packages
    - One-shot LLM setup calls guarded by CostGovernor preflight and DEFAULT_WORLDGEN_MAX_USD

key-files:
  created:
    - src/sagasmith/schemas/world.py
    - src/sagasmith/schemas/campaign_seed.py
    - src/sagasmith/prompts/oracle/world_bible_generation.py
    - src/sagasmith/prompts/oracle/campaign_seed_generation.py
    - src/sagasmith/agents/oracle/skills/world-bible-generation/SKILL.md
    - src/sagasmith/agents/oracle/skills/campaign-seed-generation/SKILL.md
    - src/sagasmith/agents/oracle/skills/world_bible_generation/logic.py
    - src/sagasmith/agents/oracle/skills/campaign_seed_generation/logic.py
    - tests/agents/oracle/test_world_bible_generation.py
    - tests/agents/oracle/test_campaign_seed_generation.py
    - tests/integration/test_world_generation_flow.py
    - tests/prompts/test_oracle_worldgen_prompts.py
  modified:
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/app/config.py
    - src/sagasmith/evals/fixtures.py
    - src/sagasmith/graph/state.py
    - src/sagasmith/schemas/__init__.py
    - src/sagasmith/schemas/export.py
    - src/sagasmith/schemas/saga_state.py
    - tests/skills_adapter/test_production_catalog.py

key-decisions:
  - "Worldgen skills are future-scoped first_slice=false so no-paid-call first-slice runs remain usable unless a deterministic fake LLM is explicitly injected."
  - "Oracle stores world_bible and campaign_seed once and skips regeneration when both are present, preserving idempotent graph re-entry."
  - "Worldgen prompts follow D-06.5 with versioned modules and JSON_SCHEMA co-located with prompt builders."

patterns-established:
  - "LLM skill logic accepts deterministic fake clients and optional provider-log collectors so tests never make paid calls."
  - "Agent Skill hyphen paths keep production catalog compatibility while underscore packages provide Python imports."

requirements-completed: [AI-01, AI-03, D-10, D-11, D-12]

duration: 9min
completed: 2026-04-28
---

# Phase 6 Plan 01: World Bible and Campaign Seed Generation Summary

**Oracle one-shot world and campaign seed generation now creates validated hidden setting context and 3-5 opening hooks before first scene planning.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-28T17:11:20Z
- **Completed:** 2026-04-28T17:20:18Z
- **Tasks:** 1 plan task / 11 implementation steps
- **Files modified:** 29

## Accomplishments

- Added strict `WorldBible` and `CampaignSeed` schema contracts with nested locations, factions, NPCs, conflicts, plot hooks, selected arc, and validation invariants.
- Implemented D-06.5 versioned Oracle prompt modules and structured-call skill logic using `invoke_with_retry`, JSON Schema validation, fake-client-compatible tests, and budget preflight.
- Wired `world_bible` and `campaign_seed` into `SagaState`, `SagaGraphState`, JSON Schema export, fixtures, and the Oracle node's play-phase path.
- Added integration coverage proving a fresh play turn generates world context exactly once before the scene brief and preserves no-paid-call behavior through `DeterministicFakeClient`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement World Bible and Campaign Seed Generation (Oracle)** - `a4faa41` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/schemas/world.py` - Hidden world bible model with unique IDs for locations, factions, NPCs, and conflicts.
- `src/sagasmith/schemas/campaign_seed.py` - Campaign seed model requiring 3-5 hooks and a selected arc that references an existing hook.
- `src/sagasmith/prompts/oracle/world_bible_generation.py` - Versioned system prompt, typed user prompt builder, and `WorldBible` JSON Schema.
- `src/sagasmith/prompts/oracle/campaign_seed_generation.py` - Versioned campaign seed prompt and `CampaignSeed` JSON Schema.
- `src/sagasmith/agents/oracle/skills/*generation/` - Agent Skill definitions plus importable Python logic for both generated context calls.
- `src/sagasmith/agents/oracle/node.py` - Runs world/seed generation once in play phase when onboarding records and an LLM client are available.
- `src/sagasmith/app/config.py` - Defines `DEFAULT_WORLDGEN_MAX_USD = 0.50` for D-06.6 setup-call cost ceiling.
- `src/sagasmith/schemas/saga_state.py` and `src/sagasmith/graph/state.py` - Add persisted graph fields for `world_bible` and `campaign_seed`.
- Tests under `tests/agents/oracle/`, `tests/integration/test_world_generation_flow.py`, and `tests/prompts/` cover validation, fake LLM generation, idempotency, and prompt rendering.

## Decisions Made

- Worldgen Agent Skills are marked `first_slice: false`; the Phase 5/early Phase 6 no-paid-call loop remains available without injecting any LLM client, while dedicated tests inject `DeterministicFakeClient`.
- The Oracle activation log records the final worldgen skill (`campaign-seed-generation`) during the combined one-shot generation pass; scene-brief logging remains unchanged when no worldgen runs.
- The plan-specified hyphenated skill directories are retained, with underscore import packages added for Python runtime imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added importable Python packages for hyphenated Agent Skill logic**
- **Found during:** Task 1 (skill logic implementation)
- **Issue:** The required skill directories `world-bible-generation` and `campaign-seed-generation` are valid Agent Skill paths but not importable Python packages.
- **Fix:** Kept plan-specified hyphenated `logic.py` wrapper files and added `world_bible_generation` / `campaign_seed_generation` import packages containing the runtime implementation.
- **Files modified:** `src/sagasmith/agents/oracle/skills/world-bible-generation/logic.py`, `src/sagasmith/agents/oracle/skills/world_bible_generation/logic.py`, `src/sagasmith/agents/oracle/skills/campaign-seed-generation/logic.py`, `src/sagasmith/agents/oracle/skills/campaign_seed_generation/logic.py`
- **Verification:** `uv run pytest` passed.
- **Committed in:** `a4faa41`

**2. [Rule 2 - Missing Critical] Updated schema export contract and tests for new LLM-boundary schemas**
- **Found during:** Acceptance verification
- **Issue:** Adding `WorldBible` and `CampaignSeed` to LLM-boundary schema export changed the expected exported schema count and schema set.
- **Fix:** Updated schema export tests and boundary model count assertions from 27 to 29 and added both schema names to the expected contract.
- **Files modified:** `tests/graph/test_routing.py`, `tests/persistence/test_migrations.py`, `tests/providers/test_models.py`, `tests/schemas/test_json_schema_export.py`
- **Verification:** Full `uv run pytest` passed.
- **Committed in:** `a4faa41`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both were necessary for runtime importability and schema-boundary correctness; no scope beyond Plan 06-01 was added.

## Known Stubs

- `src/sagasmith/agents/oracle/node.py` still emits `_FIRST_SLICE_STUB_SCENE_BRIEF` after worldgen. This is intentional and remains owned by Phase 6 Plan 06-02 (Scene Brief Composition).

## Issues Encountered

- A full-suite run surfaced an existing transient SQLite/Textual integration failure in `test_resume_after_pause_completes_turn`; rerunning that test passed, and a subsequent full `uv run pytest` passed.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src tests` — passed.
- `uv run pyright src/sagasmith/schemas/world.py src/sagasmith/schemas/campaign_seed.py src/sagasmith/prompts/oracle src/sagasmith/agents/oracle src/sagasmith/evals/fixtures.py tests/agents/oracle tests/integration/test_world_generation_flow.py tests/prompts/test_oracle_worldgen_prompts.py` — 0 errors, warnings only.
- `uv run pytest` — 507 passed, 1 skipped.

## Next Phase Readiness

- Plan 06-02 can consume `state["world_bible"]`, `state["campaign_seed"]`, and `state["memory_packet"]` when replacing the remaining Oracle scene brief stub.
- Later Phase 6 safety work still owns hard/soft policy routing and player-facing post-generation gates.

## Self-Check: PASSED

- Created files verified on disk.
- Task commit `a4faa41` verified in git history.
- Summary file verified on disk.

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
