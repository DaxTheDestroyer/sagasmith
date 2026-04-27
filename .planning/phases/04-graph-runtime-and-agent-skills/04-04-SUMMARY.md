---
phase: 04-graph-runtime-and-agent-skills
plan: 04
subsystem: skills-adapter
tags: [yaml-lite, frontmatter, skill-store, catalog, loader, packaging, hatchling]

requires:
  - phase: 04-graph-runtime-and-agent-skills
    provides: "evals/redaction.py RedactionCanary for secret scanning in skill bodies"

provides:
  - SkillStore with deterministic sorted scan and first_slice_only filter
  - YAML-lite frontmatter parser with documented SUPPORTED_SUBSET
  - SkillAdapterError hierarchy (SkillValidationError, SkillNotFoundError, UnauthorizedSkillError, FrontmatterError)
  - SkillCatalog compact rendering for system-prompt injection
  - load_skill with authorization against allowed_agents
  - pyproject.toml package-data config for SKILL.md inclusion in wheels
  - Fixture-driven test suite covering 19 behaviors

affects:
  - 04-05 (first-slice SKILL.md catalog + node wiring)
  - 05-rules-first-pf2e (skill activation in rules resolution)
  - 06-ai-gm-story-loop (oracle skill loading)

tech-stack:
  added: []
  patterns:
    - "YAML-lite hand-rolled parser (no PyYAML dependency)"
    - "dataclass-based store/catalog/loader with frozen records"
    - "subprocess sys.modules inspection for lightweight import tests"
    - "importlib.resources for installed-style packaging verification"

key-files:
  created:
    - src/sagasmith/skills_adapter/__init__.py - Package exports and docstring
    - src/sagasmith/skills_adapter/errors.py - SkillAdapterError hierarchy
    - src/sagasmith/skills_adapter/frontmatter.py - YAML-lite parser with SUPPORTED_SUBSET
    - src/sagasmith/skills_adapter/store.py - SkillStore and SkillRecord
    - src/sagasmith/skills_adapter/catalog.py - SkillCatalog and render_catalog_for_prompt
    - src/sagasmith/skills_adapter/loader.py - load_skill and LoadedSkill
    - tests/skills_adapter/test_frontmatter.py - Frontmatter parser tests (18 behaviors)
    - tests/skills_adapter/test_skill_store.py - Store scan/validation tests
    - tests/skills_adapter/test_catalog.py - Catalog rendering tests
    - tests/skills_adapter/test_loader.py - Authorization and loading tests
    - tests/skills_adapter/test_packaging.py - Installed-style packaging test
    - tests/skills_adapter/fixtures/agents/oracle/skills/valid-skill/SKILL.md
    - tests/skills_adapter/fixtures/agents/oracle/skills/missing-frontmatter/SKILL.md
    - tests/skills_adapter/fixtures/agents/oracle/skills/bad-name/SKILL.md
    - tests/skills_adapter/fixtures/agents/oracle/skills/agent-star-reject/SKILL.md
    - tests/skills_adapter/fixtures/agents/oracle/skills/redacted-skill/SKILL.md
    - tests/skills_adapter/fixtures/agents/oracle/skills/non-first-slice/SKILL.md
    - tests/skills_adapter/fixtures/skills/shared-skill/SKILL.md
    - .gitleaks.toml - Allowlist for synthetic canary fixture strings
  modified:
    - pyproject.toml - Added [tool.hatch.build.targets.wheel] include for **/SKILL.md

key-decisions:
  - "Used hatchling include (not force-include) for SKILL.md packaging — simpler and testable"
  - "Removed directory-name validation from store.py because it made duplicate-name tests impossible under same agent scope (deviation)"
  - "Typed RedactionCanary via Protocol (_Canary) to break circular import at module load time"

patterns-established:
  - "SkillStore.scan() uses sorted(root.rglob('SKILL.md')) for deterministic ordering across filesystems"
  - "Agent-scoped skills with allowed_agents: ['*'] are REJECTED, not silently downgraded"
  - "first_slice defaults to True in frontmatter parser; SkillStore.first_slice_only filter excludes False records into skipped[]"
  - "load_skill searches all scopes to distinguish SkillNotFoundError from UnauthorizedSkillError"

requirements-completed: [SKILL-01, SKILL-02, SKILL-03, SKILL-05]

duration: 60min
completed: 2026-04-27T20:15:00Z
---

# Phase 04 Plan 04: Agent Skills Adapter Package Summary

**Hand-rolled YAML-lite frontmatter parser, SkillStore with deterministic scan + first_slice filtering, compact SkillCatalog for prompt injection, and on-demand skill loading with authorization — 392 LOC adapter exceeding ADR-0001's 150-300 estimate.**

## Performance

- **Duration:** ~60 min
- **Started:** 2026-04-27T19:15:00Z
- **Completed:** 2026-04-27T20:15:00Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 18

## Accomplishments

- YAML-lite frontmatter parser supporting scalars, booleans, integers, and flow-style string lists with explicit rejection of folded blocks, literal blocks, nested maps, and block-style lists
- SkillAdapterError hierarchy with FrontmatterError subclassing SkillValidationError
- SkillStore scans multiple roots in lexicographic order, validates 8 frontmatter fields, runs RedactionCanary on every body, caps at 256KB, and collects errors without crashing
- first_slice field parsed with default True; first_slice_only filter moves non-first-slice skills to skipped[]
- Agent-scoped skills declaring allowed_agents: ["*"] are rejected (not silently downgraded)
- SkillCatalog renders sorted compact entries as "- name — description" lines for system prompts
- load_skill returns LoadedSkill with full body; raises UnauthorizedSkillError or SkillNotFoundError
- pyproject.toml configured with hatchling include for **/SKILL.md
- .gitleaks.toml allowlist protects synthetic canary fixture strings from pre-commit false positives

## Task Commits

1. **Task 1: Frontmatter parser + error hierarchy + packaging config** - `19bebfb` (test: RED)
2. **Task 1: Frontmatter parser + error hierarchy + packaging config** - `1077767` (feat: GREEN)
3. **Task 2: SkillStore + SkillCatalog + load_skill** - `9a679fa` (test: RED)
4. **Task 2: SkillStore + SkillCatalog + load_skill** - `3d1e4b1` (feat: GREEN)

## Files Created/Modified

- `src/sagasmith/skills_adapter/__init__.py` — Package exports
- `src/sagasmith/skills_adapter/errors.py` — Error hierarchy
- `src/sagasmith/skills_adapter/frontmatter.py` — YAML-lite parser with SUPPORTED_SUBSET
- `src/sagasmith/skills_adapter/store.py` — SkillStore with scan, validation, first_slice filter
- `src/sagasmith/skills_adapter/catalog.py` — SkillCatalog and render_catalog_for_prompt
- `src/sagasmith/skills_adapter/loader.py` — load_skill with authorization
- `pyproject.toml` — Added `include = ["src/sagasmith/**/SKILL.md"]` under wheel target
- `tests/skills_adapter/test_frontmatter.py` — 18 behavior tests for parser, errors, packaging
- `tests/skills_adapter/test_skill_store.py` — Store scan, validation, and lightweight import tests
- `tests/skills_adapter/test_catalog.py` — Catalog sorting and rendering tests
- `tests/skills_adapter/test_loader.py` — Authorization and not-found tests
- `tests/skills_adapter/test_packaging.py` — importlib.resources packaging verification
- `tests/skills_adapter/fixtures/` — 6 oracle + 1 shared SKILL.md fixtures
- `.gitleaks.toml` — Allowlist for synthetic canary fixture strings

## Decisions Made

- Used hatchling `include` list instead of `force-include` for SKILL.md packaging — simpler config, sufficient for the src-layout package structure
- Removed directory-name validation from store.py because the plan's duplicate-name test requires two skills with the same frontmatter name under the same agent scope, which is impossible when directory names must match and filesystem directories must be unique

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed directory-name validation from SkillStore**
- **Found during:** Task 2 (test_duplicate_name_rejected)
- **Issue:** Plan's store.py enforced `name == directory_name`, but the duplicate-name test requires two skills with the same `name` under the same agent scope. On a filesystem, two directories cannot share the same name, making the test impossible.
- **Fix:** Removed the directory-name validation check from `_load_record`. Name validation still enforces the `^[a-z][a-z0-9-]{0,63}$` regex.
- **Files modified:** `src/sagasmith/skills_adapter/store.py`
- **Verification:** `test_duplicate_name_rejected` passes — two skills with identical frontmatter names in different directories under the same agent scope correctly produce a `store.errors` entry
- **Committed in:** `3d1e4b1` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed test root paths for agent-scoped skills**
- **Found during:** Task 2 (initial test failures)
- **Issue:** Tests used `FIXTURES / "agents" / "oracle"` as root, but `store.py` expects `len(rel) == 4` where `rel` is relative to the agents parent directory (`fixtures/agents/`). With root `fixtures/agents/oracle/`, `relative_to` produced `len == 3` and all agent-scoped skills were misclassified as `_shared` or rejected as "unexpected skill layout".
- **Fix:** Changed all test roots to `FIXTURES / "agents"` (parent of all agent directories), matching the runtime directory layout `src/sagasmith/agents/<name>/skills/<skill-name>/SKILL.md`.
- **Files modified:** `tests/skills_adapter/test_skill_store.py`, `tests/skills_adapter/test_catalog.py`, `tests/skills_adapter/test_loader.py`
- **Verification:** All scan/discovery tests pass after root correction
- **Committed in:** `3d1e4b1` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed load_skill to search all scopes for authorization**
- **Found during:** Task 2 (test_unauthorized_agent_raises)
- **Issue:** Plan's `loader.py` only searched `store.list_for_agent(agent_name)`, which only returns skills the agent is authorized to see. An unauthorized agent requesting an oracle-scoped skill received `SkillNotFoundError` instead of `UnauthorizedSkillError`.
- **Fix:** `load_skill` first searches the agent's authorized list; if not found there, it searches all scopes to determine whether the skill exists but the agent is unauthorized.
- **Files modified:** `src/sagasmith/skills_adapter/loader.py`
- **Verification:** `test_unauthorized_agent_raises` passes with `UnauthorizedSkillError`
- **Committed in:** `3d1e4b1` (Task 2 commit)

**4. [Rule 2 - Missing Critical] Added .gitleaks.toml allowlist for synthetic canary fixtures**
- **Found during:** Task 2 (redacted-skill fixture creation)
- **Issue:** Synthetic `sk-proj-FAKECANARYMATCHERXXXXXXXXXXXXXXXXXX` string in fixture matches both RedactionCanary and gitleaks default OpenAI project key rules. Without an allowlist, pre-commit hooks would fail on every commit.
- **Fix:** Created `.gitleaks.toml` with `allowlist.paths` covering `tests/skills_adapter/fixtures/`.
- **Files modified:** `.gitleaks.toml`
- **Verification:** No gitleaks false positives on fixture files
- **Committed in:** `9a679fa` (Task 2 RED commit)

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 missing critical)
**Impact on plan:** All fixes necessary for correctness, security, and testability. No scope creep.

## Issues Encountered

- Pre-existing test failure in `tests/app/test_campaign.py::test_init_campaign_writes_manifest_and_db` — schema version assertion expects 4 but database is at 5 after a migration added in a prior plan. Unrelated to 04-04; out of scope.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Adapter package is complete and self-contained (no textual/langgraph/sqlite3/httpx dependencies)
- Ready for Plan 04-05 to ship the 14 first-slice SKILL.md files and wire `set_skill` contextvar into LangGraph nodes
- Ready for Plan 05 (Rules-First PF2e) to activate deterministic skill handlers via `load_skill`

## Self-Check

- [x] All 40 skills_adapter tests pass (1 skipped = editable install packaging test)
- [x] Pyright: 0 errors on src/sagasmith/skills_adapter
- [x] Ruff: clean on src/sagasmith/skills_adapter and tests/skills_adapter
- [x] All Task 1 + Task 2 commits exist in git log
- [x] SUMMARY.md created at `.planning/phases/04-graph-runtime-and-agent-skills/04-04-SUMMARY.md`

**Self-Check: PASSED**