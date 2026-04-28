# Phase 6: AI GM Story Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-28
**Phase:** 06-ai-gm-story-loop
**Mode:** discuss
**Areas discussed:** Narration Streaming Delivery, Safety Content Scanning, Oracle Call Frequency, World Bible and Campaign Entry Scope

## Gray Areas Presented

| Area | Description |
|------|-------------|
| Narration streaming delivery | How Orator tokens reach the TUI: buffered in state vs. real-time delivery |
| Safety content scanning | Pre-gate and post-gate implementation approach for SAFE-01/02/03 |
| Oracle call frequency | Once per scene vs. every turn vs. once at campaign start |
| World bible and campaign entry scope | Full LLM world-building vs. canned fixtures for Phase 6 entry |

## Decisions Made

### Narration Streaming Delivery
- **Question:** "Orator streams tokens to produce narration. How should tokens reach the TUI during a turn?"
- **Options presented:**
  - Buffer in state, render after node (Recommended)
  - Real-time token delivery
  - Hybrid: state + reactive display
- **User selected:** Buffer in state, render after node (Recommended)

### Safety Content Scanning
- **Question:** "SAFE-01/02/03 require blocking hard limits before generation and scanning prose after generation. What approach for content policy enforcement?"
- **Options presented:**
  - Keyword/regex lists only
  - Hybrid: keyword pre-gate + LLM post-gate (Recommended)
  - LLM classifier both gates
  - Keyword MVP, upgrade later
- **User selected:** Hybrid: keyword pre-gate + LLM post-gate (Recommended)

### Oracle Call Frequency
- **Question:** "How often does Oracle run to produce/update a SceneBrief?"
- **Options presented:**
  - Once per scene, re-plan on bypass (Recommended)
  - Every player turn
  - Once at campaign start only
- **User selected:** Once per scene, re-plan on bypass (Recommended)

### World Bible and Campaign Entry Scope
- **Question:** "Phase 6 includes AI-03 (Oracle produces starting hooks). How much world-building scaffolding does Phase 6 implement vs. defer?"
- **Options presented:**
  - Implement world-bible + seed as real LLM calls
  - Canned fixture for world bible/seed, real scene-brief (Recommended)
  - Seed generation only, defer world bible to Phase 7
- **User selected:** Implement world-bible + seed as real LLM calls

Note: User chose to go further than the recommended option on world bible scope — full world-bible-generation and campaign-seed-generation as real LLM calls, not canned fixtures.

## Prior Decisions Applied

From Phase 2 CONTEXT.md:
- D-01: Real LLM calls are opt-in only; default tests use DeterministicFakeClient (applied to QA-05 test design)
- D-03: JSON schema failures follow retry ladder: same-model repair → cheap-model repair → fail (applied to Oracle structured calls)

From ROADMAP.md:
- AI-11 (Archivist full memory assembly) explicitly deferred to Phase 7 (MemoryPacket stub decision D-15)
- Vault writes deferred to Phase 7 (D-11: world bible stored in graph state only)
