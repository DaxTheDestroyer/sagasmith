---
phase: 06-ai-gm-story-loop
plan: 05
subsystem: agents-memory
tags: [archivist, memory-packet, sqlite, langgraph, no-paid-call]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: [AgentServices, AgentActivationLogger, SkillStore, graph nodes]
  - phase: 05-rules-first-pf2e-vertical-slice
    provides: [play-turn graph flow, deterministic no-paid-call tests]
provides:
  - Phase 6 transcript-only MemoryPacket stub assembly
  - SQLite recent transcript context retrieval for memory packets
  - Provisional entity reference stubbing for locations, NPCs, and mentioned names
  - Oracle, Orator, and Archivist node memory context integration
affects: [phase-6-ai-gm-story-loop, phase-7-memory-vault-resume, oracle, orator, archivist]

tech-stack:
  added: []
  patterns:
    - Provider-free memory packet assembly from bounded SQLite transcript context
    - Runtime-injected transcript SQLite connection on AgentServices
    - Importable underscore package paired with Agent Skill hyphen directory

key-files:
  created:
    - src/sagasmith/agents/archivist/entity_stubs.py
    - src/sagasmith/agents/archivist/transcript_context.py
    - src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py
    - src/sagasmith/agents/archivist/skills/memory_packet_assembly/__init__.py
    - src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py
    - tests/agents/archivist/test_memory_packet_stub.py
    - tests/agents/archivist/test_transcript_context.py
    - tests/integration/test_memory_context_flow.py
  modified:
    - src/sagasmith/agents/archivist/node.py
    - src/sagasmith/agents/archivist/skills/memory-packet-assembly/SKILL.md
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/agents/orator/node.py
    - src/sagasmith/graph/bootstrap.py
    - src/sagasmith/graph/runtime.py
    - tests/agents/test_node_contracts.py
    - tests/agents/test_nodes_with_skills.py
    - tests/graph/test_checkpoints.py
    - tests/skills_adapter/test_production_catalog.py

key-decisions:
  - "Phase 6 memory assembly is transcript-only and provider-free; full vault/search retrieval remains deferred to Phase 7."
  - "memory-packet-assembly is marked first_slice=true because the stub is required for the Phase 6 no-paid-call first-slice story loop."
  - "AgentServices carries an optional transcript SQLite connection injected by GraphRuntime so nodes remain pure and do not open persistence resources themselves."

patterns-established:
  - "Bounded MemoryPacket creation drops oldest transcript rows first, then trims summary text to satisfy token_cap."
  - "Provisional memory entities use stable `{kind}_{slug}` IDs with vault_path=None and provisional=True."

requirements-completed: [D-15]

duration: 8min
completed: 2026-04-28
---

# Phase 6 Plan 05: Memory Packet Stub Assembly Summary

**Transcript-bounded MemoryPacket stubs now give Oracle and Orator recent campaign context without paid calls or full Phase 7 vault retrieval.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-28T17:01:44Z
- **Completed:** 2026-04-28T17:09:14Z
- **Tasks:** 1 plan task / 6 implementation steps
- **Files modified:** 18

## Accomplishments

- Implemented deterministic MemoryPacket assembly from SQLite transcript rows with token-cap enforcement.
- Added provisional entity stubbing for active locations, present entities, and capitalized transcript mentions.
- Wired memory context into Archivist, Oracle, and Orator nodes while preserving no-paid-call behavior.
- Added unit and integration coverage for transcript retrieval, packet bounding, entity refs, graph flow availability, and skill logging.

## Task Commits

Each task was committed atomically:

1. **Task 5: Implement Memory Packet Stub Assembly (Archivist)** - `fd66786` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/sagasmith/agents/archivist/entity_stubs.py` - Builds stable provisional `MemoryEntityRef` values from scene and transcript context.
- `src/sagasmith/agents/archivist/transcript_context.py` - Retrieves and formats recent SQLite transcript entries for a campaign.
- `src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py` - Plan-specified skill logic file for Phase 6 stub assembly.
- `src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py` - Importable Python package implementation used by nodes and tests.
- `src/sagasmith/agents/archivist/skills/memory-packet-assembly/SKILL.md` - Documents Phase 6 stub procedure, inputs, outputs, token cap, and fallback behavior.
- `src/sagasmith/agents/archivist/node.py` - Assembles and stores `memory_packet` and logs `memory-packet-assembly` activation.
- `src/sagasmith/agents/oracle/node.py` - Ensures a MemoryPacket is available before scene brief stub generation.
- `src/sagasmith/agents/orator/node.py` - Ensures a MemoryPacket is available before scene rendering stub output.
- `src/sagasmith/graph/bootstrap.py` - Adds optional `transcript_conn` to `AgentServices`.
- `src/sagasmith/graph/runtime.py` - Injects runtime SQLite connection into the service bundle without replacing custom node callables.
- `tests/agents/archivist/test_memory_packet_stub.py` - Covers model validation, token cap enforcement, entity refs, and fallback context.
- `tests/agents/archivist/test_transcript_context.py` - Covers SQLite transcript retrieval ordering and formatting.
- `tests/integration/test_memory_context_flow.py` - Covers graph memory availability and Archivist skill activation logging.
- Existing node, checkpoint, and skill catalog tests updated for memory packet integration.

## Decisions Made

- Phase 6 memory assembly intentionally uses only recent transcript rows and current graph-state fallback context; full FTS/vector/graph/vault retrieval remains Phase 7 scope.
- The Agent Skill directory keeps the required hyphenated `memory-packet-assembly` path, with an underscore import package for Python runtime imports.
- `GraphRuntime` injects the SQLite connection into the existing `AgentServices` object so patched/custom bootstraps keep their node callables.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added importable Python package for hyphenated Agent Skill logic**
- **Found during:** Task 5 (Memory Packet Stub Assembly)
- **Issue:** The planned skill directory name `memory-packet-assembly` is valid for Agent Skills but not importable as a Python package.
- **Fix:** Kept the plan-specified `logic.py` file and added `skills/memory_packet_assembly/logic.py` as the importable implementation used by nodes/tests.
- **Files modified:** `src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py`, `src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py`, `src/sagasmith/agents/archivist/skills/memory_packet_assembly/__init__.py`
- **Verification:** `uv run pytest` passed.
- **Committed in:** `fd66786`

**2. [Rule 2 - Missing Critical] Injected transcript SQLite connection through runtime services**
- **Found during:** Task 5 (Memory Packet Stub Assembly)
- **Issue:** Nodes are pure and did not have access to SQLite, but transcript-backed packet assembly requires the runtime database connection.
- **Fix:** Added optional `transcript_conn` to `AgentServices` and injected the existing runtime connection during persistent graph construction without nodes opening databases.
- **Files modified:** `src/sagasmith/graph/bootstrap.py`, `src/sagasmith/graph/runtime.py`
- **Verification:** `tests/integration/test_memory_context_flow.py` and full `uv run pytest` passed.
- **Committed in:** `fd66786`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both changes were necessary to satisfy the plan while preserving deterministic trust boundaries and no-paid-call execution.

## Known Stubs

- `src/sagasmith/agents/archivist/skills/memory_packet_assembly/logic.py` and `src/sagasmith/agents/archivist/skills/memory-packet-assembly/logic.py` intentionally implement a Phase 6 transcript-only stub. Phase 7 owns full vault, FTS5, LanceDB, NetworkX, callback, and summary retrieval.
- `src/sagasmith/agents/oracle/node.py` and `src/sagasmith/agents/orator/node.py` still use existing Phase 6 placeholder scene/narration behavior outside this plan's memory-context integration scope.

## Issues Encountered

- Full test suite initially surfaced outdated assertions expecting Archivist to log `turn-close-persistence` and expecting `memory-packet-assembly` to be excluded from first-slice skill stores. Updated those tests because the provider-free memory stub is now the Phase 6 first-slice Archivist skill.
- A custom bootstrap budget-stop regression exposed that replacing the bootstrap to inject `transcript_conn` discarded patched node callables. Fixed by injecting the connection into the existing service object at graph-build time.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src/sagasmith/agents/archivist src/sagasmith/agents/oracle/node.py src/sagasmith/agents/orator/node.py src/sagasmith/graph/bootstrap.py src/sagasmith/graph/runtime.py tests/agents/archivist tests/integration/test_memory_context_flow.py tests/agents/test_node_contracts.py tests/agents/test_nodes_with_skills.py tests/graph/test_checkpoints.py tests/skills_adapter/test_production_catalog.py` — passed.
- `uv run pyright src/sagasmith/agents/archivist src/sagasmith/agents/oracle/node.py src/sagasmith/agents/orator/node.py src/sagasmith/graph/bootstrap.py src/sagasmith/graph/runtime.py tests/agents/archivist tests/integration/test_memory_context_flow.py` — 0 errors, warnings only.
- `uv run pytest` — 498 passed, 1 skipped.

## Next Phase Readiness

- Oracle and Orator can now depend on `state["memory_packet"]` existing during Phase 6 scene-planning/rendering work.
- Phase 7 can replace the transcript-only stub with full vault-backed retrieval behind the same `MemoryPacket` contract.

## Self-Check: PASSED

- Created files verified on disk.
- Task commit `fd66786` verified in git history.
- Summary file verified on disk.

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
