---
phase: 04-graph-runtime-and-agent-skills
plan: 02
subsystem: graph-runtime
tags: [langgraph, sqlite-saver, checkpoint, activation-log, contextvar]

requires:
  - phase: 04-01
    provides: SagaGraphState, GraphBootstrap, compiled StateGraph with 5 agent nodes

provides:
  - LangGraph integration spike proving interrupt_before, checkpoint_id, thread_id semantics
  - SqliteSaver-backed persistent graph runtime (GraphRuntime)
  - Pre-narration and final CheckpointRef writes owned by runtime boundary
  - Agent activation logger with contextvar handoff for skill_name injection
  - Migration 0005 (agent_skill_log) with FK and CHECK constraints

affects:
  - 04-03 (interrupts/TUI wiring builds on runtime.py and checkpoint semantics)
  - 04-05 (node wiring uses activation_log contextvar)
  - Phase 6 (LLM nodes use persistent graph)

tech-stack:
  added:
    - langgraph-checkpoint-sqlite>=3,<4
  patterns:
    - Runtime boundary owns all persistence writes (thin-node rule)
    - ContextVar handoff for per-node metadata without plumbing changes
    - Thread identity locked to campaign:<id>

key-files:
  created:
    - src/sagasmith/graph/checkpoints.py
    - src/sagasmith/graph/activation_log.py
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/persistence/migrations/0005_agent_skill_log.sql
    - tests/graph/test_langgraph_spike.py
    - tests/graph/test_checkpoints.py
    - tests/graph/test_activation_log.py
    - tests/persistence/test_agent_skill_log.py
  modified:
    - src/sagasmith/graph/graph.py
    - src/sagasmith/graph/bootstrap.py
    - src/sagasmith/graph/__init__.py
    - src/sagasmith/persistence/repositories.py
    - src/sagasmith/persistence/__init__.py
    - src/sagasmith/schemas/persistence.py
    - src/sagasmith/schemas/__init__.py

key-decisions:
  - "Pre-narration CheckpointRef write is owned by GraphRuntime, not by TUI caller or node body"
  - "Thread identity locked to campaign:<campaign_id>; turn_id stays in state + checkpoint_refs"
  - "Archivist node does NOT call turn_close; runtime wrapper detects post-archivist state and invokes turn_close"
  - "AgentActivationLogger uses ContextVar for skill_name injection without re-plumbing node signatures"
  - "LangGraph spike test kept as permanent regression coverage for version upgrades"

patterns-established:
  - "Runtime boundary pattern: nodes stay pure; runtime wraps graph.invoke and owns DB writes"
  - "ContextVar handoff: _current_activation lets nodes call get_current_activation().set_skill(name)"
  - "Single-owner checkpoint writes: only runtime.py writes CheckpointRef rows"

requirements-completed:
  - GRAPH-02
  - GRAPH-03
  - GRAPH-05
  - AI-12

duration: ~40 min
completed: 2026-04-27
---

# Phase 4 Plan 02: Persistent Graph + Activation Log Summary

**LangGraph spike-proven persistent graph runtime with SqliteSaver, pre-narration/final checkpoint refs, and per-node activation logging via contextvar**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-04-27
- **Completed:** 2026-04-27
- **Tasks:** 3
- **Files modified:** 17

## Accomplishments

- Proved LangGraph interrupt_before, checkpoint_id extraction, Command(resume), thread isolation, and table non-collision in a permanent spike test
- Built SqliteSaver-backed GraphRuntime with interrupt_before=["orator"] compile option
- Runtime owns pre-narration CheckpointRef write when pause fires and final CheckpointRef via turn_close
- Agent activation logger (AgentActivationLogger) writes one row per node invocation with success/error/interrupted outcomes
- ContextVar _current_activation enables downstream nodes to set skill_name without signature changes
- Migration 0005 creates agent_skill_log with FK to turn_records, CHECK constraints, and two indices
- All 29 new tests pass; full suite (334+) green

## Task Commits

Each task was committed atomically:

1. **Task 1: LangGraph integration spike** — `eba0272` (test)
2. **Task 2: Migration 0005 + AgentSkillLogRecord + AgentSkillLogRepository + AgentActivationLogger** — `36ded66` (feat)
3. **Task 3: Persistent graph runtime** — `de4207a` (feat)

## Files Created/Modified

- `src/sagasmith/graph/checkpoints.py` — SqliteSaver builder, CheckpointKind enum, checkpoint_id extractor
- `src/sagasmith/graph/activation_log.py` — AgentActivationLogger with contextvar handoff + RedactionCanary guard
- `src/sagasmith/graph/runtime.py` — GraphRuntime owning pre-narration/final CheckpointRef writes and turn_close
- `src/sagasmith/persistence/migrations/0005_agent_skill_log.sql` — agent_skill_log table schema
- `src/sagasmith/persistence/repositories.py` — AgentSkillLogRepository
- `src/sagasmith/schemas/persistence.py` — AgentSkillLogRecord Pydantic model
- `tests/graph/test_langgraph_spike.py` — 6 spike tests proving LangGraph contract
- `tests/graph/test_checkpoints.py` — 9 tests for persistent graph behavior
- `tests/graph/test_activation_log.py` — 10 tests for logger + contextvar
- `tests/persistence/test_agent_skill_log.py` — Schema and repository tests

## Decisions Made

- Runtime boundary owns all CheckpointRef writes (not nodes, not TUI) — preserves thin-node rule
- Thread_id convention locked to `campaign:<campaign_id>` per Codex review Option A
- Budget precheck_estimated(0.0) deferred to Phase 6 — no dead-code call sites
- Activation logger contextvar stub ships here; Plan 04-05 fills set_skill calls

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Subagent completion signal not received (Copilot runtime limitation). Spot-checks confirmed all commits, tests, and files created successfully. SUMMARY.md created by orchestrator post-hoc.

## Next Phase Readiness

- Runtime and checkpoint semantics proven and tested
- Ready for 04-03 (native interrupts + TUI wiring + E2E smoke)
- Ready for 04-05 (SKILL.md catalog + node wiring using contextvar handoff)

---
*Phase: 04-graph-runtime-and-agent-skills*
*Completed: 2026-04-27*
