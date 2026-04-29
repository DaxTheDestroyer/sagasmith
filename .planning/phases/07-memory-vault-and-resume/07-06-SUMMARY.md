---
phase: 07-memory-vault-and-resume
plan: 06
subsystem: memory-vault-qa
tags: [qa, vault, resume, leakage-regression, release-gate]

requires:
  - phase: 07-memory-vault-and-resume
    provides: [archivist enrichment, player-vault sync, resume warning, repair CLI]
provides:
  - GM-leakage regression coverage for player-vault projection
  - quit/resume integration coverage for vault pages, rolling summary, memory retrieval, and session increment
  - full local pytest validation for Phase 7 code paths
affects: [phase-7-completion, phase-8-hardening]

key-files:
  created:
    - src/sagasmith/agents/archivist/skills/vault-page-upsert/SKILL.md
  modified:
    - src/sagasmith/agents/archivist/node.py
    - src/sagasmith/agents/oracle/node.py
    - src/sagasmith/agents/archivist/skills/vault_page_upsert/logic.py
    - src/sagasmith/graph/runtime.py
    - src/sagasmith/graph/state.py
    - src/sagasmith/schemas/saga_state.py
    - src/sagasmith/vault/__init__.py
    - src/sagasmith/vault/page.py
    - src/sagasmith/vault/resolver.py
    - tests/app/test_campaign.py
    - tests/skills_adapter/test_production_catalog.py
    - tests/vault/test_sync.py

requirements-completed: [QA-06, QA-08, QA-09]
completed: 2026-04-29
---

# Phase 7 Plan 06: QA and Release Gate Summary

Wave 6 QA is complete for the memory/vault/resume slice.

## Accomplishments

- Fixed `SagaState`/`SagaGraphState` drift by adding `vault_pending_writes` while avoiding vault/schema circular imports.
- Made Archivist vault writes checkpoint-safe by serializing `VaultPage` payloads through LangGraph and reconstructing them at `resume_and_close`.
- Preserved direct-node contract tests by returning `VaultPage` objects when the Archivist is not running under the persistent graph runtime.
- Fixed canonical entity IDs such as `npc_mira_warden` so vault upsert and resolver do not double-prefix IDs.
- Ensured session-end close authors `sessions/session_NNN.md`, rebuilds derived indices, and syncs the player vault after the turn is marked complete.
- Added Oracle-side Phase 7 memory assembly with vault/FTS/graph retrieval when a vault service is available.
- Updated player-vault foreshadowed stub behavior to preserve required frontmatter fields while stripping GM-only fields and body content.
- Updated production skill catalog expectations for new Archivist skills and moved `vault-page-upsert` SKILL.md into a hyphenated discovery directory.

## Verification

- `uv run pytest tests/vault/test_player_projection.py tests/cli/test_vault_cmd.py tests/agents/archivist/test_end_to_end_memory.py tests/integration/test_quit_resume_flow.py -x` passed.
- `uv run pytest -x` passed: 768 passed, 2 skipped.
- `uv run ruff check .` passed before final documentation updates.
- `uv run pyright` still reports pre-existing strict typing errors across older modules/tests; Wave 6 runtime/vault tests are green.

## Notes

- Full Phase 7 behavior is provider-free for the tested QA path except scripted fake responses used for rolling summary tests.
- Remaining pyright cleanup should be handled as a dedicated type-hardening task rather than mixed into Phase 7 QA fixes.
