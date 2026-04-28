---
phase: 06-ai-gm-story-loop
plan: 04
subsystem: orator-scene-rendering
tags: [orator, scene-rendering, safety, streaming, dice-ux, mechanical-consistency, langgraph, prompts, no-paid-call]

requires:
  - phase: 06-ai-gm-story-loop
    provides: [oracle scene brief composition, beat_ids, content-policy pre-gate (06-02)]
  - phase: 06-ai-gm-story-loop
    provides: [memory packet stub (06-05)]
  - phase: 06-ai-gm-story-loop
    provides: [SafetyPostGate, SafetyPreGate, QA-05 regression (06-07)]
  - phase: 04-graph-runtime-and-agent-skills
    provides: [AgentServices, AgentActivationLogger, SkillStore, graph interrupts]
provides:
  - Buffered stream-after-classify Orator narration pipeline (D-06.1)
  - Inline hard-limit pattern matcher for early stream cancellation
  - SafetyPostGate integration with two-rewrite ladder and fallback
  - Deterministic mechanical-consistency audit (D-06.2)
  - Dice UX mode handling (auto, reveal, hidden)
  - resolved_beat_ids emission per D-06.4
  - Per-turn budget wiring per D-06.6
  - Orator scene rendering prompt module per D-06.5
affects: [phase-6-ai-gm-story-loop, orator, safety, scene-rendering, graph-routing]

tech-stack:
  added: []
  patterns:
    - Buffered stream-after-classify: accumulate tokens, validate gates, then playback
    - Inline hard-limit matcher compiled from ContentPolicy.hard_limits
    - Deterministic regex mechanical-consistency audit (no LLM verifier)
    - D-06.5 prompt module with CheckResult constraint tokens
    - Two-rewrite ladder shared between post-gate and mechanics audit

key-files:
  created:
    - src/sagasmith/agents/orator/dice_ux.py
    - src/sagasmith/agents/orator/mechanics_consistency.py
    - src/sagasmith/agents/orator/skills/scene_rendering/logic.py
    - src/sagasmith/prompts/orator/scene_rendering.py
    - src/sagasmith/services/safety_inline_matcher.py
    - tests/agents/orator/test_scene_rendering.py
    - tests/agents/orator/test_mechanics_consistency.py
    - tests/integration/test_scene_rendering_flow.py
    - tests/services/test_safety_inline_matcher.py
  modified:
    - src/sagasmith/agents/orator/node.py
    - src/sagasmith/agents/orator/skills/scene-rendering/SKILL.md
    - tests/agents/test_node_contracts.py
    - tests/integration/test_tui_graph_smoke.py

key-decisions:
  - "SafetyPostGate from 06-07 is reused directly; this plan does not duplicate the service."
  - "Inline hard-limit matcher runs on accumulated buffer text, not per-token, to catch multi-word patterns."
  - "Mechanical-consistency audit uses degree-of-success keyword tables; actor_id parameter reserved for Phase 7 per-actor filtering."
  - "Beat resolution uses keyword overlap heuristic between narration and beat text; Phase 7 may refine."
  - "Two-rewrite budget is shared between post-gate blocks, post-gate rewrites, and mechanics audit failures."

patterns-established:
  - "Orator pipeline: stream → inline-match → post-gate → mechanics-audit → playback → rewrite ladder → fallback"
  - "resolved_beat_ids merged into existing list via dict.fromkeys for dedup"
  - "No-LLM deterministic fallback produces fallback narration preserving no-paid-call behavior"

requirements-completed: [AI-07, AI-08, AI-09, AI-10, SAFE-01, SAFE-02, SAFE-03, D-01, D-02, D-04, D-05]

duration: 25min
completed: 2026-04-28
---

# Phase 6 Plan 04: Scene Rendering with Safety Gates Summary

**Buffered stream-after-classify Orator pipeline with inline hard-limit matcher, SafetyPostGate, deterministic mechanics audit, dice UX modes, and resolved_beat_ids emission.**

## Performance

- **Duration:** 25 min
- **Tasks:** 1 composite plan task / 7 implementation steps
- **Files modified:** 13 (9 created, 4 modified)

## Accomplishments

- Replaced stub Orator narration with the D-06.1 buffered stream-after-classify pipeline that accumulates LLM tokens in a private buffer, validates through inline hard-limit matcher + SafetyPostGate + mechanical-consistency audit before any tokens reach `pending_narration`.
- Implemented `SafetyInlineMatcher` with compiled regex patterns from `ContentPolicy.hard_limits` for zero-cost per-token-window hard-limit detection during streaming.
- Implemented deterministic mechanical-consistency audit (D-06.2) with degree-of-success keyword tables and actor-action consistency checking — no second LLM verifier.
- Added dice UX mode handling (auto/reveal/hidden) with prompt-side constraint encoding so the LLM respects the player's chosen dice visibility.
- Orator now emits `resolved_beat_ids` per D-06.4 using keyword-overlap heuristic against beat text.
- Per-turn budget wiring (D-06.6) preflight-checks before generation and emits fallback narration on `BudgetStopError`.
- D-06.5 prompt module encodes `CheckResult` payloads as structured constraint tokens with explicit "do not contradict" instructions.
- Two-rewrite ladder shared between post-gate blocks/rewrites and mechanics audit failures; fallback narration after exhaustion.

## Task Commits

1. **Scene rendering with safety gates** - `1da74ec` (feat)

## Files Created/Modified

- `src/sagasmith/agents/orator/dice_ux.py` — Dice UX mode handling with prompt instructions for auto/reveal/hidden modes.
- `src/sagasmith/agents/orator/mechanics_consistency.py` — Deterministic post-generation audit with degree-of-success keyword tables.
- `src/sagasmith/agents/orator/skills/scene_rendering/logic.py` — Core buffered stream-after-classify pipeline with rewrite ladder.
- `src/sagasmith/prompts/orator/scene_rendering.py` — D-06.5 versioned prompt with CheckResult constraint tokens and JSON schema.
- `src/sagasmith/services/safety_inline_matcher.py` — Compiled regex scanner for ContentPolicy hard_limits during streaming.
- `src/sagasmith/agents/orator/node.py` — Replaced stub with real pipeline; emits resolved_beat_ids; honors D-06.6 budget.
- `src/sagasmith/agents/orator/skills/scene-rendering/SKILL.md` — Enhanced with detailed procedure, inputs, outputs, dice UX modes.
- `tests/agents/orator/test_scene_rendering.py` — 11 unit tests for pipeline, dice UX, inline matcher, and resolved beats.
- `tests/agents/orator/test_mechanics_consistency.py` — 10 unit tests for deterministic audit.
- `tests/services/test_safety_inline_matcher.py` — 9 unit tests for compiled regex matcher.
- `tests/integration/test_scene_rendering_flow.py` — 8 integration tests for full pipeline, safety enforcement, dice UX, skill logging.
- `tests/agents/test_node_contracts.py` — Updated for new fallback narration text.
- `tests/integration/test_tui_graph_smoke.py` — Updated for new fallback narration text.

## Decisions Made

- SafetyPostGate from 06-07 is reused directly; this plan does not duplicate the service.
- Inline hard-limit matcher runs on accumulated buffer text (every 50 tokens), not per-token, to catch multi-word patterns while maintaining streaming performance.
- Mechanical-consistency audit uses degree-of-success keyword tables with `actor_id` parameter reserved for Phase 7 per-actor filtering.
- Beat resolution uses keyword overlap heuristic between narration text and beat text; Phase 7 may refine with LLM-assisted detection.
- Two-rewrite budget (2 rewrites max) is shared between post-gate blocks/rewrites and mechanics audit failures to prevent excessive retry loops.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] SafetyPostGate already exists from 06-07**
- **Found during:** Step 2 implementation
- **Issue:** Plan Step 2 specified "Implement Safety Post-Gate Service" but 06-07 already created `safety_post_gate.py` with full inline scanner + LLM classifier + verdict types.
- **Fix:** Reused existing SafetyPostGate directly. The Orator pipeline integrates it via the `render_scene` function.
- **Files modified:** None (existing service used as-is)
- **Verification:** All 87 affected tests pass, including 06-07 safety tests.
- **Committed in:** `1da74ec`

**2. [Rule 2 - Missing Critical] Updated existing tests for new fallback narration**
- **Found during:** Test regression check
- **Issue:** Two existing tests (`test_node_contracts.py`, `test_tui_graph_smoke.py`) expected the old stub narration "You take a moment to assess the scene." which no longer exists.
- **Fix:** Updated assertions to expect "The scene shifts. A new detail draws your attention." — the deterministic fallback when no LLM is available.
- **Files modified:** `tests/agents/test_node_contracts.py`, `tests/integration/test_tui_graph_smoke.py`
- **Verification:** All 653 tests pass (1 skipped).
- **Committed in:** `1da74ec`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both changes were necessary: reusing the existing SafetyPostGate avoided duplication, and updating tests was required because the pipeline changed the deterministic fallback text.

## Known Stubs

- `src/sagasmith/agents/orator/mechanics_consistency.py` — `actor_id` parameter is reserved for Phase 7 per-actor filtering; current implementation performs broad keyword matching without actor scoping.
- `src/sagasmith/agents/orator/skills/scene_rendering/logic.py` — `_detect_resolved_beats` uses keyword overlap heuristic; Phase 7 may add LLM-assisted beat resolution.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: llm_narration | `src/sagasmith/agents/orator/skills/scene_rendering/logic.py` | Orator now generates LLM narration through `LLMClient.stream`. Safety gates (inline matcher, post-gate, mechanics audit) mitigate content policy violations. |

## Issues Encountered

- A flaky SQLite checkpoint `OperationalError` in `test_rules_first_vertical_slice` appeared during the full suite run but passes in isolation — pre-existing issue unrelated to this plan.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check` on all new/modified files — passed.
- `uv run pytest tests/agents/orator/ tests/services/test_safety_inline_matcher.py tests/integration/test_scene_rendering_flow.py tests/agents/test_node_contracts.py tests/agents/test_nodes_with_skills.py tests/integration/test_scene_management_flow.py tests/integration/test_tui_graph_smoke.py tests/services/test_safety_post_gate.py` — 87 passed.
- `uv run pytest` — 653 passed, 1 skipped.

## Next Phase Readiness

- Orator now produces real LLM narration through a safety-validated pipeline, ready for Plan 06-06 (narration recovery) and 06-08 (integration testing).
- `resolved_beat_ids` is populated by Orator, enabling Oracle replanning when all beats are resolved.
- SafetyPostGate integration is complete; Plan 06-08 can test the full pipeline end-to-end.

## Self-Check: PASSED

- Created files verified on disk.
- Task commit `1da74ec` verified in git history.
- Summary file verified on disk.

---
*Phase: 06-ai-gm-story-loop*
*Completed: 2026-04-28*
