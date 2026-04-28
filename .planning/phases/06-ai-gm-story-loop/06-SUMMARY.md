# Phase 6: AI GM Story Loop - Implementation Summary

**Planned:** 2026-04-28
**Owner:** Kilo (AI Assistant)
**Phase:** 06-ai-gm-story-loop
**Requirements:** AI-01 through AI-10, GRAPH-06, GRAPH-07, SAFE-01 through SAFE-03, QA-05

## Overview

This document summarizes the implementation plans for Phase 6: AI GM Story Loop of the SagaSmith project. The phase focuses on implementing the AI-driven narrative generation while maintaining strict boundaries between deterministic mechanics and AI-generated content.

## Key Components

### 1. Oracle Agent Implementation
- **World Bible Generation**: Create initial campaign world context
- **Campaign Seed Generation**: Generate starting hooks aligned with player preferences
- **Scene Brief Composition**: Plan scenes with beats, outcomes, and pacing
- **Content Policy Routing**: Pre-filter content based on safety policies

### 2. RulesLawyer Agent Enhancement
- **Intent-to-Proposal Layer**: Convert natural language to mechanical proposals
- **Deterministic Resolution**: Maintain existing deterministic rules processing
- **Skill/Combat Resolution**: Handle both skill checks and combat actions

### 3. Orator Agent Implementation
- **Scene Rendering**: Generate player-facing narration with LLM streaming
- **Dice UX Handling**: Respect configured dice visibility modes
- **Safety Post-Gate**: Scan and filter generated content for policy violations
- **Mechanical Consistency**: Ensure narration aligns with resolved mechanics

### 4. Archivist Agent Stub
- **Memory Packet Assembly**: Provide bounded context without full implementation
- **Token Cap Enforcement**: Maintain performance boundaries

### 5. Graph Runtime Enhancement
- **Narration Recovery**: Handle incomplete narration turns
- **Deterministic Stability**: Preserve outcomes across narration retries
- **Checkpoint Management**: Manage pre-narration and final checkpoints

### 6. Safety Infrastructure
- **Pre-Gate Filtering**: Block prohibited content before generation
- **Post-Gate Scanning**: Filter generated content with LLM classifier
- **Event Logging**: Track all safety interventions
- **Regression Testing**: Verify content policy enforcement

### 7. Integration and Quality Assurance
- **Full Turn Flow Testing**: Validate complete player interaction cycle
- **Safety Enforcement Testing**: Verify all safety mechanisms
- **Recovery Mechanism Testing**: Ensure robustness against interruptions
- **No-Paid-Call Smoke Tests**: Enable testing without LLM costs

## Cross-cutting design decisions

Six decisions in `06-PLAN.md` ("Cross-cutting design decisions") MUST be locked before tasks start:

- **D-06.1** Buffered stream-after-classify (resolves streaming vs post-gate conflict)
- **D-06.2** Prompt-side constraints + deterministic regex audit for mechanical consistency (no second LLM verifier)
- **D-06.3** Pre-gate returns routing verdicts (`Allowed`/`Rerouted`/`Blocked`); Oracle posts `SAFETY_BLOCK` interrupt
- **D-06.4** Explicit `resolved_beat_ids: list[str]` on `SagaState`, populated by Orator
- **D-06.5** Prompts live under `src/sagasmith/prompts/<agent>/<skill>.py` with version stamps and snapshot tests
- **D-06.6** Per-call budget wiring through existing `BudgetStopError` for every LLM-touching task

## Implementation Order (dependency-respecting)

1. **Task 5 (Memory Packet Stub)** — unblocks Tasks 2 and 4
2. **Task 1 (World Bible/Campaign Seed)** and **Task 3 (Intent-to-Proposal)** — independent, parallel
3. **Task 2 (Scene Brief Composition)** — needs Task 5
4. **Task 7 pre-gate half** — can land alongside Task 2 (D-06.3 wiring point)
5. **Task 4 (Scene Rendering)** — needs Tasks 2 + 5; depends on D-06.1 / D-06.2 being decided; on the critical path
6. **Task 7 post-gate half** — must land with Task 4
7. **Task 6 (Narration Discard + Recovery Commands)** — small; any time after Task 4 starts
8. **Task 8 (Integration Testing)** — incremental as tasks land; final pass after all merges

## Success Criteria

All Phase 6 requirements will be met when:

1. User can receive 3-5 starting hooks or a curated first-slice hook aligned with onboarding preferences
2. Oracle produces validated scene plans and replans around player choices without emitting player-facing narration
3. RulesLawyer converts player intent into deterministic mechanical proposals/results without letting LLMs invent modifiers, DCs, damage, HP, action counts, or degrees
4. Orator is the only player-facing narrative voice, streams at least one complete beat per completed turn, respects dice UX, and does not contradict resolved mechanics
5. Unsafe scene intents or generated prose are blocked, rerouted, retried, or safely degraded, and incomplete narration can be retried or discarded without changing deterministic outcomes

## Files Created

- `06-PLAN.md` - Overall phase plan
- `06-01-PLAN.md` - Task 1: World Bible and Campaign Seed Generation
- `06-02-PLAN.md` - Task 2: Scene Brief Composition
- `06-03-PLAN.md` - Task 3: Intent-to-Proposal Layer
- `06-04-PLAN.md` - Task 4: Scene Rendering with Safety Gates
- `06-05-PLAN.md` - Task 5: Memory Packet Stub Assembly
- `06-06-PLAN.md` - Task 6: Narration Recovery Mechanisms
- `06-07-PLAN.md` - Task 7: Safety Event Logging and Testing
- `06-08-PLAN.md` - Task 8: Integration Testing and Quality Assurance

## Timeline

**Total Estimated Duration:** 2–3 weeks (matches `06-PLAN.md`)
**Parallelizable Work:** Tasks 1, 3, and 5 in parallel up front; then Tasks 2 + 6 in parallel after Task 5
**Critical Path:** Task 5 → Task 2 → Task 4 → Task 7 post-gate → Task 8

## Risk Mitigation

Key risks and their mitigations:

1. **LLM Cost Control**: Use retry ladders, cheap models, and bounded context
2. **Safety Policy Failures**: Implement dual-layer safety with comprehensive testing
3. **Deterministic Instability**: Use checkpointing to freeze outcomes before narration
4. **Performance Issues**: Token-capped MemoryPacket and efficient pattern matching
5. **Integration Complexity**: Incremental development with continuous testing

This implementation will deliver a robust AI GM story loop that maintains the trust boundaries essential to the SagaSmith architecture while providing engaging narrative experiences for players.