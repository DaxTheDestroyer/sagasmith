---
phase: 04-graph-runtime-and-agent-skills
plan: 03
subsystem: graph-interrupts
tags: [langgraph, interrupt, tui, safety, budget, e2e]

requires:
  - phase: 04-01
    provides: SagaGraphState, compiled StateGraph, 5 agent node stubs
  - phase: 04-02
    provides: GraphRuntime, SqliteSaver, activation logger, checkpoint semantics

provides:
  - InterruptKind enum + InterruptEnvelope with RedactionCanary guard
  - Native LangGraph interrupt/resume via update_state + Command(resume)
  - BudgetStopError → InterruptKind.BUDGET_STOP translation at runtime boundary
  - /pause and /line dual-write (SafetyEvent + graph interrupt)
  - TUI runtime wires GraphRuntime into SagaApp
  - End-to-end smoke test: TUI input → graph → stub narration → /pause

affects:
  - 04-05 (node wiring uses interrupt primitives)
  - Phase 6 (BudgetStopError emission from LLM nodes)
  - Phase 8 (RetconCommand will use InterruptKind.RETCON)

tech-stack:
  added: []
  patterns:
    - Native LangGraph update_state + Command(resume) for caller-side signals
    - Runtime-level exception translation (nodes never see interrupt types)
    - Dual-write pattern: SafetyEvent + graph interrupt for /pause and /line

key-files:
  created:
    - src/sagasmith/graph/interrupts.py
    - tests/graph/test_interrupts.py
    - tests/tui/test_commands_post_interrupts.py
    - tests/integration/test_tui_graph_smoke.py
  modified:
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/graph/state.py
    - src/sagasmith/graph/__init__.py
    - src/sagasmith/tui/runtime.py
    - src/sagasmith/tui/app.py
    - src/sagasmith/tui/commands/safety.py
    - src/sagasmith/tui/commands/control.py

key-decisions:
  - "Native LangGraph primitives: update_state + Command(resume) instead of shadow pending_interrupt field"
  - "BudgetStopError translation lives ONLY in runtime wrapper; node bodies remain interrupt-agnostic"
  - "RetconCommand is acknowledge-only in Phase 4; Phase 8 owns full confirmation + rollback"
  - "last_interrupt is a single-slot state field; second post_interrupt overwrites the first"
  - "Graceful degrade when app.graph_runtime is None preserves Phase 3 CLI test contract"

patterns-established:
  - "Runtime exception translation: catch domain errors at graph boundary, convert to interrupts"
  - "Dual-write commands: persist SafetyEvent AND post graph interrupt when bound"

requirements-completed:
  - GRAPH-04

duration: ~35 min
completed: 2026-04-27
---

# Phase 4 Plan 03: Native Interrupts + TUI Wiring + E2E Smoke Summary

**LangGraph native interrupt/resume primitives wired to TUI commands with end-to-end smoke test proving TUI → graph → stub narration path**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-27
- **Completed:** 2026-04-27
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- InterruptKind enum with PAUSE, LINE, RETCON, BUDGET_STOP, SESSION_END
- InterruptEnvelope frozen dataclass with RedactionCanary payload guard
- GraphRuntime.post_interrupt uses LangGraph update_state; resume_after_interrupt uses Command(resume)
- BudgetStopError caught in runtime wrapper and translated to BUDGET_STOP interrupt — nodes never reference interrupt types
- /pause and /line commands preserve Phase 3 SafetyEvent writes AND post graph interrupts when runtime bound
- RetconCommand remains stub-only (no interrupt) — Phase 8 scope explicitly documented
- build_app() constructs GraphRuntime and attaches to SagaApp; --headless-status path unchanged
- End-to-end smoke test under tests/integration/ proves full TUI → graph → narration → /pause path
- 18 new tests pass; full suite (403+) green

## Task Commits

Each task was committed atomically:

1. **Task 1: InterruptKind + InterruptEnvelope + post/resume helpers** — `73522b2` (feat)
2. **Task 2: Wire GraphRuntime into TUI + extend /pause and /line** — `e1e9a7f` (feat)
3. **Task 3: End-to-end TUI → graph → stub narration smoke test** — (included in e1e9a7f)

## Files Created/Modified

- `src/sagasmith/graph/interrupts.py` — InterruptKind, InterruptEnvelope, extract_pending_interrupt
- `src/sagasmith/graph/runtime.py` — post_interrupt, resume_after_interrupt, BudgetStopError translation
- `src/sagasmith/graph/state.py` — added last_interrupt field to SagaGraphState and SagaState
- `src/sagasmith/tui/runtime.py` — build_app constructs GraphRuntime, build_graph_runtime flag
- `src/sagasmith/tui/app.py` — graph_runtime attribute on SagaApp
- `src/sagasmith/tui/commands/safety.py` — PauseCommand + LineCommand post interrupts when bound
- `src/sagasmith/tui/commands/control.py` — RetconCommand stub preserved, no interrupt plumbing
- `tests/graph/test_interrupts.py` — 9 tests for interrupt primitives
- `tests/tui/test_commands_post_interrupts.py` — 5 tests for command interrupt wiring
- `tests/integration/test_tui_graph_smoke.py` — 4 async end-to-end tests

## Decisions Made

- Used LangGraph native update_state + Command(resume) instead of interrupt() inside nodes — keeps node code simple
- Single-slot last_interrupt semantics documented; queue deferred to Phase 8 if needed
- Graceful degrade pattern: every command checks `if app.graph_runtime is not None` before posting

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Subagent completion signal not received (Copilot runtime limitation). Spot-checks confirmed all commits, tests, and files created successfully. SUMMARY.md created by orchestrator post-hoc.

## Next Phase Readiness

- Interrupt primitives proven and wired to TUI
- Ready for 04-05 (SKILL.md catalog + node wiring)
- Ready for Phase 6 (BudgetStopError emission from LLM-aware nodes)

---
*Phase: 04-graph-runtime-and-agent-skills*
*Completed: 2026-04-27*
