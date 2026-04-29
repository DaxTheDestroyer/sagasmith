---
phase: 07-memory-vault-and-resume
plan: 04
subsystem: memory-vault
status: complete
tags: [archivist, vault, visibility, rolling-summary, session-pages, canon-conflict]

requires:
  - phase: 07-memory-vault-and-resume
    provides: [vault foundation, vault page upsert, memory packet assembly]
provides:
  - visibility promotion skill for gm_only → foreshadowed → player_known transitions
  - LLM-backed rolling summary update with token-cap enforcement
  - end-of-session session page authoring with frontmatter, beats, and roll tables
  - non-blocking canon-conflict warning stub
affects: [07-05-player-vault-sync-recap-resume, 07-06-qa, 08-retcon-repair]

tech-stack:
  added: []
  patterns:
    - underscore Python packages with hyphenated Agent Skill compatibility wrappers
    - TDD red/green commits per Archivist skill surface

key-files:
  created:
    - src/sagasmith/agents/archivist/skills/visibility-promotion/SKILL.md
    - src/sagasmith/agents/archivist/skills/visibility_promotion/logic.py
    - src/sagasmith/agents/archivist/skills/rolling-summary-update/SKILL.md
    - src/sagasmith/agents/archivist/skills/rolling_summary_update/logic.py
    - src/sagasmith/agents/archivist/skills/session-page-authoring/SKILL.md
    - src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py
    - src/sagasmith/agents/archivist/skills/canon-conflict-detection/SKILL.md
    - src/sagasmith/agents/archivist/skills/canon_conflict_detection/logic.py
    - tests/archivist/test_visibility_promotion.py
    - tests/archivist/test_rolling_summary.py
    - tests/archivist/test_session_authoring.py
    - tests/archivist/test_canon_conflict.py
  modified:
    - src/sagasmith/agents/archivist/node.py

key-decisions:
  - "Hyphenated Agent Skill directories use thin wrappers around underscore Python packages so skill discovery paths remain human-readable while imports remain valid Python."
  - "Canon-conflict detection is intentionally non-blocking in 07-04: it logs a structured warning and returns an empty list until full extraction/routing is implemented."
  - "Session page authoring derives only from completed turn records, transcript entries, and roll logs to avoid importing GM-only vault content into player-visible session history."

patterns-established:
  - "Archivist skill packages expose deterministic logic through underscore imports and hyphenated SKILL.md compatibility directories."
  - "Rolling summary updates are LLM text completions constrained by prompt wording and post-call token-cap truncation."

requirements-completed: [VAULT-03, VAULT-05, VAULT-08, AI-11]

duration: 6min
completed: 2026-04-29
---

# Phase 7 Plan 04: Archivist Memory Enrichment Skills Summary

**Archivist memory enrichment now promotes spoiler-safe visibility, updates bounded rolling summaries, writes end-of-session history pages, and logs canon-conflict warning stubs.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-29T08:30:34Z
- **Completed:** 2026-04-29T08:36:29Z
- **Tasks:** 3 completed
- **Files modified:** 21

## Accomplishments

- Added TDD-covered visibility-promotion logic and wired Archivist node activation/integration.
- Added rolling-summary-update skill using the existing `LLMClient.complete` protocol with canonical prompt constraints and token-cap truncation.
- Added session-page-authoring skill that writes `sessions/session_NNN.md` from completed SQLite turn/transcript/roll records.
- Added canon-conflict-detection MVP stub that emits structured warnings without blocking play.

## Task Commits

Each task was committed atomically with TDD gates:

1. **Task 1 RED: Visibility promotion tests** - `1eb1b73` (test)
2. **Task 1 GREEN: Visibility promotion implementation** - `c030860` (feat)
3. **Task 2 RED: Rolling summary tests** - `c5e7c0f` (test)
4. **Task 2 GREEN: Rolling summary implementation** - `af1fc0c` (feat)
5. **Task 3 RED: Session authoring/conflict tests** - `3491af9` (test)
6. **Task 3 GREEN: Session authoring/conflict implementation** - `725a02b` (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `src/sagasmith/agents/archivist/node.py` - Integrates new Archivist skills, summary boundary update, visibility promotion, conflict stub, and session page authoring on session end.
- `src/sagasmith/agents/archivist/skills/visibility-promotion/SKILL.md` - Skill metadata/instructions for visibility promotion.
- `src/sagasmith/agents/archivist/skills/visibility-promotion/logic.py` - Hyphen-path compatibility wrapper.
- `src/sagasmith/agents/archivist/skills/visibility_promotion/logic.py` - One-way spoiler-safe visibility heuristic.
- `src/sagasmith/agents/archivist/skills/rolling-summary-update/SKILL.md` - Skill metadata/instructions for rolling summary updates.
- `src/sagasmith/agents/archivist/skills/rolling-summary-update/logic.py` - Hyphen-path compatibility wrapper.
- `src/sagasmith/agents/archivist/skills/rolling_summary_update/logic.py` - LLM-backed summary update and cap enforcement.
- `src/sagasmith/agents/archivist/skills/session-page-authoring/SKILL.md` - Skill metadata/instructions for session pages.
- `src/sagasmith/agents/archivist/skills/session-page-authoring/logic.py` - Hyphen-path compatibility wrapper.
- `src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py` - Session markdown/frontmatter/roll-table authoring.
- `src/sagasmith/agents/archivist/skills/canon-conflict-detection/SKILL.md` - Skill metadata/instructions for conflict stub.
- `src/sagasmith/agents/archivist/skills/canon-conflict-detection/logic.py` - Hyphen-path compatibility wrapper.
- `src/sagasmith/agents/archivist/skills/canon_conflict_detection/logic.py` - Structured warning stub returning no conflicts.
- `tests/archivist/test_visibility_promotion.py` - Visibility promotion behavior coverage.
- `tests/archivist/test_rolling_summary.py` - Rolling summary LLM/cap behavior coverage.
- `tests/archivist/test_session_authoring.py` - Session page frontmatter/beat/roll coverage.
- `tests/archivist/test_canon_conflict.py` - Conflict stub warning coverage.

## Decisions Made

- Hyphenated skill directories now wrap underscore import packages, matching the existing memory-packet pattern and preserving both Agent Skills naming and valid Python imports.
- Rolling summary uses `LLMClient.complete` with `response_format="text"` because the current provider protocol does not expose `invoke_structured` for raw text.
- Session pages are authored from SQLite transcript/roll records rather than reading arbitrary vault pages, preventing accidental GM-only leakage in player-visible session history.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used existing LLMClient protocol instead of unavailable invoke_structured**
- **Found during:** Task 2 (rolling-summary-update)
- **Issue:** The plan referenced `llm_client.invoke_structured`, but the project interface exposes `LLMClient.complete` / `stream`.
- **Fix:** Implemented text completion through `LLMClient.complete` with `response_format="text"` and post-call token cap enforcement.
- **Files modified:** `src/sagasmith/agents/archivist/skills/rolling_summary_update/logic.py`
- **Verification:** `uv run pytest tests/archivist/test_rolling_summary.py -x`
- **Committed in:** `af1fc0c`

**2. [Rule 2 - Missing Critical] Added Python-importable underscore packages for hyphenated skill directories**
- **Found during:** Tasks 1-3
- **Issue:** Hyphenated Agent Skill directory names cannot be imported as Python packages.
- **Fix:** Added underscore implementation packages plus hyphenated wrapper modules for compatibility with skill discovery paths.
- **Files modified:** all new `*_promotion`, `*_update`, `*_authoring`, and `*_detection` packages and wrappers
- **Verification:** all plan tests import and pass
- **Committed in:** `c030860`, `af1fc0c`, `725a02b`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both adjustments were required for compatibility with existing project interfaces and skill naming conventions. No scope creep.

## Known Stubs

- `src/sagasmith/agents/archivist/skills/canon_conflict_detection/logic.py` - Intentional MVP stub per plan: logs `canon_conflict_stub` warning and returns `[]` without raising or routing conflicts.
- `src/sagasmith/agents/archivist/skills/session_page_authoring/logic.py` - `quests_closed` and `callbacks_paid_off` are currently empty lists because reliable close/payoff inference is outside this plan; future phases can enrich session metadata from canonical quest/callback state.

## Threat Flags

None - new trust surfaces match the plan threat model (LLM summary update, player-visible session page generation, and non-blocking conflict stub).

## Issues Encountered

- Full `pyright` over all existing archivist tests still reports pre-existing warnings/errors in `tests/archivist/test_vault_page_upsert.py`; verification for new files passes with 0 errors and 5 warnings limited to pre-existing dynamic context-style code in visibility promotion.

## Verification

- `uv run pytest tests/archivist/test_visibility_promotion.py -x` ✅
- `uv run pytest tests/archivist/test_rolling_summary.py -x` ✅
- `uv run pytest tests/archivist/test_session_authoring.py -x` ✅
- `uv run pytest tests/archivist/test_canon_conflict.py -x` ✅
- `uv run ruff check src/sagasmith/agents/archivist tests/archivist` ✅
- `uv run pyright src/sagasmith/agents/archivist/skills/visibility_promotion src/sagasmith/agents/archivist/skills/rolling_summary_update src/sagasmith/agents/archivist/skills/session_page_authoring src/sagasmith/agents/archivist/skills/canon_conflict_detection tests/archivist/test_visibility_promotion.py tests/archivist/test_rolling_summary.py tests/archivist/test_session_authoring.py tests/archivist/test_canon_conflict.py` ✅ (0 errors, 5 warnings)

## TDD Gate Compliance

- RED commits present: `1eb1b73`, `c5e7c0f`, `3491af9`
- GREEN commits present after RED: `c030860`, `af1fc0c`, `725a02b`
- REFACTOR commits: none needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 07-05: player-vault sync, repair commands, `/recap`, and quit/resume can consume the visibility state transitions, rolling summary, session page artifacts, and conflict warning surface.

## Self-Check: PASSED

- Created skill/test files exist on disk.
- Task commits exist in git log.
- `07-04-SUMMARY.md` created in the phase directory.

---
*Phase: 07-memory-vault-and-resume*
*Completed: 2026-04-29*
