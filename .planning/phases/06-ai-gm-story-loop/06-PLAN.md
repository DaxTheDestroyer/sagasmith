# Phase 6: AI GM Story Loop - Plan

**Planned:** 2026-04-28
**Owner:** Kilo (AI Assistant)
**Phase:** 06-ai-gm-story-loop
**Requirements:** AI-01 through AI-10, GRAPH-06, GRAPH-07, SAFE-01 through SAFE-03, QA-05

## Overview

This plan implements the AI GM Story Loop for SagaSmith, enabling users to play AI-planned and AI-narrated turns while maintaining trust boundaries between deterministic rules and narrative generation. The implementation focuses on three core agents:

1. **OracleAgent** - Plans scenes and generates world content
2. **RulesLawyerAgent** - Converts player intent to mechanical proposals
3. **OratorAgent** - Renders scene plans and mechanics into player-facing narration

## Implementation Approach

The plan follows a modular approach where each agent is enhanced with LLM capabilities while preserving existing deterministic services. Key integration points include:

- Safety gates (pre-generation and post-generation content filtering)
- Graph checkpointing for narration recovery
- Memory packet stubbing for context management
- Cost governance for LLM calls

## Cross-cutting design decisions

These decisions are referenced by multiple tasks. Lock them down before any task starts.

### D-06.1 Streaming vs post-gate safety (resolves Task 4 / Task 7 tension)

**Decision: buffered "stream-after-classify" with cheap inline pre-classification.**

Rationale: a true token-by-token live stream is incompatible with a post-generation LLM classifier that may force a rewrite — the player has already seen the prohibited content. Two-rewrite limits and fallback narration make sense only when nothing has been shown yet.

Concrete mechanics:
- Orator calls `LLMClient.stream` and accumulates tokens into a private buffer.
- An **inline hard-limit pattern matcher** (regex/keyword from `ContentPolicy.hard_limits`) runs as tokens arrive. A hit cancels the stream early and triggers the rewrite ladder; this is cheap and bounded.
- Once generation completes (or after early cancel), the **post-gate LLM classifier** runs against the full buffered text. Up to two rewrites; on the third failure, fallback narration is emitted.
- Only after the post-gate passes do tokens flow into `pending_narration` and the TUI. The "stream" that the player sees is a **playback of validated tokens** at a paced rate — visually identical to live streaming, but safety-correct.
- The "first token < 2s p50" criterion is **redefined as "first validated token visible within 2s p50 of the player's input."** This is achievable because the cheap-model fallback in `invoke_with_retry` plus inline hard-limit matching avoids the worst-case classifier path on the happy path.

### D-06.2 Mechanical-consistency strategy (resolves Task 4 Step 6)

**Decision: prompt-side constraint encoding + post-generation regex audit; no second LLM verifier in Phase 6.**

- The Orator prompt receives `CheckResult` payloads as **structured constraint tokens** (e.g. `{"actor":"pc_1","check":"athletics","degree":"success","damage":7}`) and an explicit instruction to never contradict them.
- After generation, a deterministic audit pass scans buffered prose for number tokens and degree-of-success keywords, comparing them to the `CheckResult` payload. Mismatches (e.g. prose says "miss" when degree is `success`, or quotes a different damage number) trigger one rewrite using the same retry budget as the post-gate.
- A second LLM verifier is explicitly out of scope for Phase 6 (cost + latency). Phase 7 may add one if audit miss rate is high in eval.

### D-06.3 Pre-gate blocking pathway (resolves Task 7 wiring)

**Decision: pre-gate raises a routing signal, not an exception.**

- `safety_pre_gate` returns one of: `Allowed`, `Rerouted(new_intent)`, `Blocked(reason)`.
- Oracle's `content-policy-routing` skill consumes the result. On `Blocked`, Oracle posts an `InterruptKind.SAFETY_BLOCK` envelope via `runtime.post_interrupt` and the graph halts before scene-brief composition.
- On `Rerouted`, Oracle continues with the substituted intent and logs a `SafetyEvent`.
- This avoids exception-based control flow and integrates with the existing `InterruptEnvelope` machinery in [graph/interrupts.py](src/sagasmith/graph/interrupts.py).

### D-06.4 Beat resolution detection (resolves Task 2)

**Decision: explicit `resolved_beat_ids: list[str]` field on `SagaState`, populated by Orator.**

- The Orator's scene-rendering skill returns, alongside narration, the set of beat IDs from the active `SceneBrief` that its prose advanced or completed.
- Oracle's routing condition becomes: re-plan when `resolved_beat_ids` is a superset of `scene_brief.beats` OR when `player-choice-branching` flags a bypass. No heuristic guessing.
- This requires extending `SceneBrief.beats` from `list[str]` to a list of IDs (or adding a parallel `beat_ids` list). Decide in Task 2 Step 1.

### D-06.5 Prompt strategy

**Location:** `src/sagasmith/prompts/<agent>/<skill_name>.py` — one module per skill, exporting:
- `SYSTEM_PROMPT: str` — static, version-stamped at the top of the file (`PROMPT_VERSION = "2026-04-28-1"`)
- `def build_user_prompt(...) -> str` — typed function that takes the skill's input contract and returns the user message
- `JSON_SCHEMA: dict` — for structured calls; co-located with the prompt that elicits it

**Versioning:** prompt version is included in `ProviderLogRecord` metadata so we can correlate model output quality with prompt revisions.

**Testing:** every prompt module has a snapshot test under `tests/prompts/` that pins the rendered system+user output against a known input fixture. Changing a prompt requires updating the snapshot, which surfaces in code review.

### D-06.6 Cost governance wiring

Every LLM-touching task in this phase MUST honor the existing `BudgetStopError` path:

- World-bible / campaign-seed generation (Task 1): one-shot per campaign; counts against the per-campaign budget. Failure surfaces as a setup-time error.
- Scene-brief composition (Task 2): per-turn budget check before the call. On `BudgetStopError`, Oracle returns the prior scene brief unchanged and posts `BUDGET_STOP`.
- Intent-to-proposal (Task 3): cheap-model-first; falls through to deterministic-only routing on budget exhaustion (player sees "I didn't catch that — try `/check athletics 15`").
- Scene rendering (Task 4): per-turn budget covers initial generation + up to two rewrites. Exhaustion triggers fallback narration, not retry.
- Post-gate classifier (Task 7): runs on the cheap model; counts against the same per-turn budget as rendering.

Per-turn and per-campaign budget ceilings live in `app/config.py` and are documented in Task 1's acceptance criteria.

## Tasks

### Task 1: Implement World Bible and Campaign Seed Generation (Oracle)

**Requirements:** AI-01, AI-03, D-10, D-11, D-12

**Description:** 
Implement the world-bible-generation and campaign-seed-generation skills for the Oracle agent to create the initial world context and starting hooks.

**Subtasks:**
1. Create `WorldBible` Pydantic model with fields for locations, factions, NPCs, and themes
2. Create `CampaignSeed` Pydantic model with fields for plot hooks and initial arc
3. Implement `world-bible-generation` skill using LLM structured JSON calls
4. Implement `campaign-seed-generation` skill using LLM structured JSON calls
5. Add world_bible and campaign_seed fields to SagaState/SagaGraphState
6. Update Oracle node to call these skills at campaign start
7. Add routing logic to skip world/campaign generation after first run

**Acceptance Criteria:**
- World bible contains coherent setting elements aligned with player profile
- Campaign seed produces 3-5 distinct hooks matching player preferences
- Both models validate against JSON Schema
- World/campaign data persists in graph state

### Task 2: Implement Scene Brief Composition (Oracle)

**Requirements:** AI-01, AI-02, AI-04, D-07, D-08, D-09

**Description:**
Replace the stub SceneBrief with a real LLM-powered implementation that generates scene plans based on player input, memory context, and campaign state.

**Subtasks:**
1. Decide beat-id representation per D-06.4 (extend `SceneBrief.beats` to IDs OR add parallel `beat_ids`); SceneBrief otherwise already has the required fields per STATE_SCHEMA.md and does not need extending
2. Implement `scene-brief-composition` skill using LLM structured JSON calls (prompt module per D-06.5)
3. Implement `player-choice-branching` skill for re-planning on player bypasses
4. Implement `content-policy-routing` skill consuming pre-gate verdicts per D-06.3
5. Update Oracle node to use real skills instead of stub
6. Add conditional routing logic that checks `resolved_beat_ids` per D-06.4 and `player-choice-branching` bypass flags
7. Wire cost governance per D-06.6 (per-turn budget check; on `BudgetStopError`, return prior scene brief and post `BUDGET_STOP`)

**Acceptance Criteria:**
- SceneBrief includes all required fields (intent, beats, success/failure outs, etc.)
- Oracle re-plans when player bypasses planned beats
- SceneBriefs never contain player-facing narration (AI-02)
- Content policy routing blocks/redlines prohibited content

### Task 3: Implement Intent-to-Proposal Layer (RulesLawyer)

**Requirements:** AI-06, D-16, D-17

**Description:**
Add an LLM layer to the RulesLawyer that converts natural language player input into mechanical proposals before passing to deterministic services.

**Subtasks:**
1. Implement intent-resolution service capability for parsing player input
2. Create `CheckProposal` generation logic using LLM structured calls
3. Update RulesLawyer node to use LLM intent parsing before deterministic resolution
4. Maintain existing deterministic resolution for actual dice/math
5. Add routing to skip mechanics when no action is detected

**Acceptance Criteria:**
- Player input like "roll athletics dc 15" generates appropriate CheckProposal
- Natural language actions are converted to mechanical proposals
- LLM-authored math/DCs/modifiers never reach deterministic services
- Non-mechanical input routes directly to narration

### Task 4: Implement Scene Rendering with Safety Gates (Orator)

**Requirements:** AI-07, AI-08, AI-09, AI-10, SAFE-01, SAFE-02, SAFE-03, D-01, D-02, D-04, D-05

**Description:**
Replace the stub narration with streaming LLM-generated prose that respects safety policies and mechanical outcomes.

**Subtasks:**
1. Implement `scene-rendering` skill using LLM streaming with the **buffered stream-after-classify** pattern from D-06.1
2. Add dice UX mode handling (auto, reveal, hidden)
3. Implement inline hard-limit pattern matcher (cancels stream early on hits) per D-06.1
4. Implement safety post-gate scanning with cheap LLM classifier; two-rewrite limit; then fallback narration
5. Update Orator node to playback validated tokens to `pending_narration`; emit `resolved_beat_ids` per D-06.4
6. Add deterministic mechanical-consistency audit per D-06.2 (no second LLM verifier)
7. Wire cost governance per D-06.6 (per-turn budget covers initial generation + up to two rewrites)

**Acceptance Criteria:**
- Orator is the only player-facing narrative voice
- Narration respects configured dice UX modes
- Generated prose never contradicts mechanical outcomes (verified by D-06.2 audit)
- Safety post-gate blocks/redlines prohibited content
- First *validated* token visible within 2 seconds p50 of player input (per D-06.1 redefinition)

### Task 5: Implement Memory Packet Stub Assembly (Archivist)

**Requirements:** D-15

**Description:**
Create a minimal MemoryPacket implementation for Phase 6 that provides basic context without full memory assembly.

**Subtasks:**
1. Implement memory-packet-assembly stub skill
2. Create minimal MemoryPacket with recent transcript context
3. Add entity reference stubbing
4. Implement token cap enforcement
5. Integrate with Oracle and Orator node calls

**Acceptance Criteria:**
- MemoryPacket stays within token cap
- Recent context is available to agents
- Entity references are properly stubbed
- No dependency on full Archivist implementation

### Task 6: Implement Narration Discard + Recovery Commands (Graph + TUI)

**Requirements:** GRAPH-06, GRAPH-07, D-13, D-14

**Description:**
Add the missing pieces for narration recovery. Pre-narration checkpointing and incomplete-turn detection already exist in `graph/runtime.py` from Phase 4 — the gaps are the discard flow, TurnRecord status transitions, and TUI commands.

**Subtasks:**
1. Implement `discard_incomplete_turn(turn_id)` on `GraphRuntime` that loads the `CheckpointRef(kind="pre_narration")` row, updates the graph thread to that checkpoint, and marks the `TurnRecord` as `discarded`
2. Add TurnRecord status transitions: `pending_narration` → `narrated` | `discarded` | `retried`
3. Implement `retry_narration(turn_id)` on `GraphRuntime` (rewinds to pre-narration checkpoint, clears `pending_narration`, re-invokes Orator)
4. Add a regression test that asserts `check_results` and other deterministic state are byte-identical across one happy turn vs. retry-then-complete vs. discard-then-redo
5. Add TUI commands `/retry` and `/discard` to `tui/commands/`

**Acceptance Criteria:**
- Incomplete narration can be retried from pre_narration checkpoint
- Deterministic outcomes (dice rolls, HP changes) remain unchanged on retry
- Incomplete turns can be discarded without affecting state
- Recovery preserves all non-narration state

### Task 7: Implement Safety Event Logging and Testing (Safety)

**Requirements:** SAFE-01, SAFE-02, SAFE-03, QA-05, D-06

**Description:**
Complete the safety infrastructure and add comprehensive testing for content policy enforcement.

**Subtasks:**
1. Implement safety-pre-gate service capability using keyword matching
2. Implement safety-post-gate service capability using cheap LLM classifier
3. Add SafetyEvent logging for all safety actions
4. Create QA-05 regression test using DeterministicFakeClient
5. Add content policy violation fixtures for testing

**Acceptance Criteria:**
- Hard limits are blocked before generation
- Soft limits are faded/redlined appropriately
- Post-generation scanning blocks prohibited prose
- QA-05 test verifies prohibited content never reaches player
- All safety events are properly logged

### Task 8: Integration Testing and Quality Assurance

**Requirements:** All Phase 6 requirements

**Description:**
Comprehensive testing of the integrated AI GM story loop with focus on trust boundaries and safety.

**Subtasks:**
1. Create integration tests for full turn flow (Oracle → RulesLawyer → Orator)
2. Add tests for safety policy enforcement
3. Test narration recovery mechanisms
4. Verify deterministic outcome stability
5. Test content policy routing and post-gate filtering
6. Add smoke tests for no-paid-call execution
7. Verify all agent skill activations are logged

**Acceptance Criteria:**
- Full turn flow works from player input to narration
- Safety policies are properly enforced at all gates
- Deterministic outcomes remain stable across narration retries
- No prohibited content appears in player-facing output
- All LLM calls are properly logged and cost-tracked
- Integration tests pass with deterministic fake client

## Dependencies

- Phase 5 (Rules-First PF2e Vertical Slice) must be complete
- LangGraph runtime with checkpointing (Phase 4)
- Deterministic services (Phase 2)
- Onboarding and player profiles (Phase 3)

## Success Criteria

1. User can receive 3-5 starting hooks or a curated first-slice hook aligned with onboarding preferences
2. Oracle produces validated scene plans and replans around player choices without emitting player-facing narration
3. RulesLawyer converts player intent into deterministic mechanical proposals/results without letting LLMs invent modifiers, DCs, damage, HP, action counts, or degrees
4. Orator is the only player-facing narrative voice, streams at least one complete beat per completed turn, respects dice UX, and does not contradict resolved mechanics
5. Unsafe scene intents or generated prose are blocked, rerouted, retried, or safely degraded, and incomplete narration can be retried or discarded without changing deterministic outcomes

## Risks and Mitigations

**Risk:** LLM calls exceed budget or produce inconsistent output
**Mitigation:** Use retry ladder with cheap model fallback, implement strict schema validation, add cost governance

**Risk:** Safety policies fail to block prohibited content
**Mitigation:** Implement dual-layer safety (pre-gate keyword filtering + post-gate LLM scanning), add comprehensive regression tests

**Risk:** Deterministic outcomes change on narration retries
**Mitigation:** Use pre_narration checkpointing to freeze all state before narration begins

**Risk:** Memory context becomes too large or unfocused
**Mitigation:** Use token-capped MemoryPacket stubs, implement strict context boundaries

## Timeline

**Estimated Duration:** 2–3 weeks (revised from earlier 5–7 day estimate, which did not account for the streaming/safety design work in D-06.1, the prompt infrastructure in D-06.5, and the per-task cost-governance wiring in D-06.6).

**Dependency-respecting order:**
1. **Task 5 (Memory packet stub)** — unblocks Tasks 2 and 4
2. **Task 1 (World/campaign generation)** and **Task 3 (Intent-to-proposal)** — independent, can run in parallel
3. **Task 2 (Scene-brief composition)** — needs Task 5
4. **Task 4 (Scene rendering)** — needs Task 2 and Task 5; depends on D-06.1 / D-06.2 being decided
5. **Task 7 (Safety infrastructure)** — pre-gate (D-06.3) can land alongside Task 2; post-gate must land with Task 4
6. **Task 6 (Narration recovery)** — small; can land any time after Task 4 is in flight
7. **Task 8 (Integration testing)** — incremental as each task lands; final pass after all tasks merge

**True parallelism:** Tasks 1, 3, and 5 can run concurrently. After Task 5 lands, Tasks 2 and 6 can run concurrently. Task 4 is the critical-path bottleneck.

## Validation

**Unit Tests:** Each agent skill and service capability has unit tests
**Integration Tests:** Full turn flow tested with deterministic fake client
**Safety Tests:** Content policy enforcement verified with regression tests
**Smoke Tests:** No-paid-call execution verified
**Manual Testing:** End-to-end gameplay validation

---
*Plan created: 2026-04-28*
*Phase: 06-ai-gm-story-loop*