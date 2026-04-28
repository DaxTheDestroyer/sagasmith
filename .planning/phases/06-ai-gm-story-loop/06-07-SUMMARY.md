---
phase: 06-ai-gm-story-loop
plan: 07
subsystem: safety
tags: [safety, content-policy, pre-gate, post-gate, regression, qa-05]

requires:
  - phase: 06-ai-gm-story-loop
    provides: memory-packet-stub (06-05)
  - phase: 06-ai-gm-story-loop
    provides: oracle-scene-brief-composition (06-02)
provides:
  - SafetyPreGate service with compiled keyword/regex patterns
  - SafetyPostGate service with inline scanner + cheap LLM classifier
  - QA-05 regression test framework with content policy violation fixtures
  - Enhanced SafetyEventService with Phase 6 event categories
  - Pre-gate routing verdict integration in Oracle node
  - Post-gate integration hooks in Orator node
affects: [06-04-scene-rendering, 06-08-integration-testing]

tech-stack:
  added: []
  patterns: [safety-pre-gate-verdict, safety-post-gate-verdict, regex-co-occurrence-synonyms]

key-files:
  created:
    - src/sagasmith/services/safety_pre_gate.py
    - src/sagasmith/services/safety_post_gate.py
    - tests/fixtures/content_policy_violations.py
    - tests/integration/test_safety_services.py
    - tests/regression/test_content_policy_safety.py
    - tests/services/test_safety_pre_gate.py
    - tests/services/test_safety_post_gate.py
  modified:
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py
    - src/sagasmith/agents/orator/node.py
    - src/sagasmith/persistence/migrations/0004_safety_events.sql
    - src/sagasmith/schemas/persistence.py
    - src/sagasmith/services/safety.py

key-decisions:
  - "SafetyPreGate returns verdict objects (Allowed/Rerouted/Blocked) — never raises exceptions per D-06.3"
  - "SafetyPostGate runs inline hard-limit scanner first (free), then cheap LLM classifier only if inline passes"
  - "Two-rewrite limit enforced by Orator pipeline, not post-gate service — keeps service stateless"
  - "Loose regex co-occurrence patterns (child.{0,30}harm) separated from word-boundary exact matches for pattern compilation"
  - "Safety event logging failures roll back connection to prevent SQLite connection state corruption"

patterns-established:
  - "Safety verdict types: frozen dataclass hierarchy (PreGateVerdict → Allowed/Rerouted/Blocked)"
  - "Pattern compilation: exact synonyms with word-boundary regex + loose co-occurrence patterns without boundary wrapper"

requirements-completed: [SAFE-01, SAFE-02, SAFE-03, QA-05, D-06]

duration: 35min
completed: 2026-04-28
---

# Phase 06: AI GM Story Loop — Plan 07 Summary

**Safety pre-gate and post-gate services with D-06.3 verdict routing, QA-05 regression framework, and 82 safety-specific tests**

## Performance

- **Duration:** 35 min (including orchestrator recovery from empty signal)
- **Tasks:** 1 (composite)
- **Files modified:** 13 (7 created, 6 modified)

## Accomplishments
- Implemented `SafetyPreGate` with compiled keyword/regex patterns returning Allowed/Rerouted/Blocked verdicts
- Implemented `SafetyPostGate` with deterministic inline scanner + cheap LLM classifier fallback
- Created QA-05 regression test framework with hard-limit, soft-limit, boundary, and multilingual fixtures
- Added `pre_gate_block` and `pre_gate_reroute` event kinds to safety_events CHECK constraint
- Enhanced SafetyEventService with Phase 6 logging methods (log_pre_gate_block, log_pre_gate_reroute, log_post_gate_rewrite, log_fallback)
- Integrated pre-gate routing into Oracle node and post-gate hooks into Orator node
- Added loose regex co-occurrence patterns for `harm_to_children` to catch variations like "A child is seriously harmed"

## Task Commits

1. **Safety pre/post-gate + tests** - `fd63742` (feat)

## Files Created/Modified
- `src/sagasmith/services/safety_pre_gate.py` — Pre-generation content-policy gate with compiled patterns
- `src/sagasmith/services/safety_post_gate.py` — Post-generation safety gate with inline scanner + LLM classifier
- `tests/fixtures/content_policy_violations.py` — Deterministic violation fixtures for QA-05
- `tests/integration/test_safety_services.py` — Pre-gate and post-gate integration tests
- `tests/regression/test_content_policy_safety.py` — QA-05 comprehensive regression tests
- `tests/services/test_safety_pre_gate.py` — Unit tests for pre-gate service
- `tests/services/test_safety_post_gate.py` — Unit tests for post-gate service
- `src/sagasmith/agents/oracle/node.py` — Oracle safety event logging with connection rollback
- `src/sagasmith/agents/oracle/skills/content_policy_routing/logic.py` — Loose regex co-occurrence patterns
- `src/sagasmith/agents/orator/node.py` — Orator post-gate safety logging with connection rollback
- `src/sagasmith/persistence/migrations/0004_safety_events.sql` — Added pre_gate_block, pre_gate_reroute to CHECK
- `src/sagasmith/schemas/persistence.py` — Extended safety event schema
- `src/sagasmith/services/safety.py` — Phase 6 safety event logging methods

## Decisions Made
- Pre-gate is a pure function (unit-testable without runtime) — Oracle posts SAFETY_BLOCK interrupt, not the gate
- Post-gate is stateless — two-rewrite limit enforced by Orator pipeline
- Loose regex co-occurrence patterns compiled separately from word-boundary exact matches
- Safety event logging failures roll back connection to prevent state corruption

## Deviations from Plan

### Auto-fixed Issues

**1. SQLite connection state corruption from safety event logging**
- **Found during:** Full test suite run
- **Issue:** `_log_safety_event_to_service` swallowed exceptions but left SQLite connection in a failed-transaction state, causing subsequent `AgentSkillLogRepository.append` to assert
- **Fix:** Added `safety_svc.conn.rollback()` in exception handler
- **Verification:** Full test suite passes (615 passed, 1 skipped)

**2. Loose regex patterns wrapped in word-boundary markers**
- **Found during:** Safety pre-gate unit tests
- **Issue:** `child.{0,30}harm` pattern wrapped in `\b...\b` wouldn't match "child is seriously harmed" because `harm` is mid-word in "harmed"
- **Fix:** Compiled loose regex patterns separately without word-boundary wrapper
- **Verification:** All 82 safety-specific tests pass

## Issues Encountered
- Executor returned empty result twice (known runtime issue) — resolved via spot-check verification and manual commit
- Dice roll timestamp test flaky when run in full suite but passes in isolation — pre-existing, unrelated

## Next Phase Readiness
- Safety infrastructure ready for Orator scene rendering (06-04)
- Post-gate service ready for buffered stream-after-classify pipeline
- QA-05 regression framework ready for integration testing (06-08)

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
