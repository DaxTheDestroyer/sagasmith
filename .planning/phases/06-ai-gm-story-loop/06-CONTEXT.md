# Phase 6: AI GM Story Loop - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

User can play AI-planned and AI-narrated turns where:
- Oracle produces validated `SceneBrief`s per scene and re-plans on player bypasses
- RulesLawyer converts player intent into deterministic mechanical proposals/results
- Orator is the only player-facing voice, renders scene plans + resolved mechanics into narration
- Safety gates block/reroute/rewrite prohibited content before and after generation
- The graph can recover from or discard an incomplete narration turn

Phase 6 does not implement: full Archivist memory assembly (AI-11, Phase 7), vault writes (Phase 7), world-bible persistence to vault (Phase 7), or retcon confirmation/rollback (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Narration Streaming Delivery
- **D-01:** Orator accumulates all streamed tokens into `pending_narration` in LangGraph graph state. The TUI reads and renders `pending_narration` after the node completes. No real-time token-by-token delivery to the TUI in Phase 6.
- **D-02:** Node purity is maintained — Orator node returns a state dict update with `pending_narration` populated; the runtime/TUI layer owns rendering. No async queues or callbacks from inside graph nodes.

### Safety Content Scanning
- **D-03:** Pre-generation gate (SAFE-01/SAFE-02): Oracle's `content-policy-routing` skill uses keyword/pattern matching against `ContentPolicy.hard_limits` and `soft_limits` string lists to block or reroute scene beats before Orator runs. Fast, zero extra LLM cost, consistent with the existing `RedactionCanary` pattern-match model.
- **D-04:** Post-generation gate (SAFE-03): After Orator accumulates prose, a cheap LLM classifier call scans the text against `ContentPolicy` before the narration is written to `pending_narration`. On violation: request one rewrite attempt; if the second attempt also fails, fall back to a safe terse fallback line. Log every event via `SafetyEventService.log_fallback()`.
- **D-05:** The cheap LLM classifier call for the post-gate uses the configured `cheap_model`, counts against the session budget via CostGovernor, and is logged with `llm-call-logging`.
- **D-06:** QA-05 is implemented using `DeterministicFakeClient` scripted to return hard-limit trigger content; the test asserts those strings do not appear in `pending_narration` after the safety post-gate runs.

### Oracle Call Frequency and Re-Plan Trigger
- **D-07:** Oracle runs once per scene (not once per turn) to produce a `SceneBrief` with multiple beats. A scene persists across multiple player turns until a beat is resolved, bypassed, or the scene concludes.
- **D-08:** Re-planning triggers when: (a) the player explicitly bypasses or rejects a planned beat, detected by the `player-choice-branching` skill comparing `pending_player_input` against `scene_brief.beats`; or (b) all beats in the current `SceneBrief` are resolved (scene complete). Outside these triggers, the existing `SceneBrief` stays active.
- **D-09:** The graph routing check for "does Oracle need to run?" is a conditional edge in `graph.py`: if `scene_brief` is `None` or all beats resolved or bypass detected → route to oracle_node; otherwise → skip Oracle and route directly to rules_lawyer_node (or orator_node if no mechanics needed).

### World Bible and Campaign Entry Scope
- **D-10:** Phase 6 implements `world-bible-generation` and `campaign-seed-generation` as real LLM structured-JSON calls using onboarding outputs (`PlayerProfile`, `ContentPolicy`, `HouseRules`). These run once at campaign start before the first scene.
- **D-11:** World bible output is stored in graph state (not vault) in Phase 6. Vault persistence for `WorldBible` and `CampaignSeed` is deferred to Phase 7 when vault writes are available.
- **D-12:** Oracle's hook list (AI-03) comes from `campaign-seed-generation`: 3-5 hooks aligned with `PlayerProfile.pillar_weights` and `tone`. The player selects or is curated into one hook to begin the first scene. The first hook selection is the entry trigger for `scene-brief-composition`.

### Narration Recovery (GRAPH-06 / GRAPH-07)
- **D-13:** Recovery from incomplete narration reuses the existing `pre_narration` checkpoint. The runtime detects `snapshot.next == ("orator",)` for the same `turn_id` and re-runs from the Orator interrupt forward, replacing `pending_narration` with a fresh narration attempt. `check_results` and `scene_brief` are frozen at the pre-narration checkpoint so deterministic outcomes (GRAPH-07) are unchanged on retry.
- **D-14:** "Discard the incomplete turn" path: the runtime reverts to the pre-narration checkpoint by loading the stored `CheckpointRef(kind="pre_narration")` for the current `turn_id`. The `TurnRecord.status` stays non-complete, making the turn detectable as discarded. This does not require a new graph node.

### MemoryPacket Stub (Phase 7 deferred)
- **D-15:** For Phase 6, Oracle and Orator receive a minimal stub `MemoryPacket` constructed by the runtime/bootstrap layer: empty `entities`, empty `callbacks`, minimal transcript context (last 3 transcript entries from SQLite), within the configured token cap. Full Archivist memory assembly (AI-11) remains Phase 7 scope.

### RulesLawyer Phase 6 Role
- **D-16:** RulesLawyer in Phase 6 adds the LLM intent-to-proposal layer on top of Phase 5's deterministic services: it uses a structured LLM call to convert `pending_player_input` into a `CheckProposal` list, then calls Phase 5 deterministic services (`RulesEngine`, `CombatEngine`) to resolve them. LLMs do not compute dice math, modifiers, DCs, or HP.
- **D-17:** When `pending_player_input` is pure narrative with no mechanical action (e.g., "I look around the tavern"), RulesLawyer returns an empty `check_results` list and routes to Orator directly.

### the agent's Discretion
- Exact prompt templates for Oracle scene-brief-composition and Orator scene-rendering
- Exact `WorldBible` and `CampaignSeed` Pydantic model field set (add to schemas/ as needed)
- Whether Oracle bypass detection is keyword-based or a lightweight LLM call
- Graph checkpoint timing within a scene (planner may add per-beat checkpoints if needed)
- Specific SafetyGuard fallback narration text

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning Scope
- `.planning/ROADMAP.md` — Phase 6 goal, dependencies, requirements (AI-01–AI-10, GRAPH-06/07, SAFE-01/02/03, QA-05), and success criteria.
- `.planning/REQUIREMENTS.md` — Full text of AI-01 through AI-10, GRAPH-06, GRAPH-07, SAFE-01, SAFE-02, SAFE-03, QA-05.
- `.planning/PROJECT.md` — Trust-before-breadth principle, LLM-agents-propose / deterministic-services-validate split, out-of-scope boundaries.

### Product and Runtime Specs
- `docs/sagasmith/GAME_SPEC.md` §3.2 — OracleAgent behavior contract: SceneBrief fields, hook generation, re-planning, callback tracking, AI-02 prohibition.
- `docs/sagasmith/GAME_SPEC.md` §3.3 — OratorAgent behavior contract: dice UX modes, prose constraints, streaming target, AI-07/08/09/10.
- `docs/sagasmith/GAME_SPEC.md` §3.4 — RulesLawyerAgent behavior contract: intent-to-proposal, deterministic resolution.
- `docs/sagasmith/GAME_SPEC.md` §3.6 — SafetyGuard two-phase contract: pre-gate + post-gate, two-rewrite limit, fallback.
- `docs/sagasmith/GAME_SPEC.md` §4 — Turn flow observable behavior.
- `docs/sagasmith/LLM_PROVIDER_SPEC.md` — Retry ladder (§7), streaming contract (§6), secrets (§8), cheap_model config (§4).
- `docs/sagasmith/STATE_SCHEMA.md` — SceneBrief, MemoryPacket, CheckProposal, CheckResult, StateDelta, SagaState schemas.

### Agent Skills Catalogs
- `docs/sagasmith/agents/oracle-skills.md` — world-bible-generation (§2.1), campaign-seed-generation (§2.2), scene-brief-composition (§2.3), player-choice-branching (§2.4), inline-npc-creation (§2.7), content-policy-routing (§2.9), first-slice required skills (§3).
- `docs/sagasmith/agents/services-capabilities.md` — safety-pre-gate (§2.2), safety-post-gate (§2.3), intent-resolution (§2.1), cost-governor (§2.4), llm-call-logging (§2.10).

### SKILL.md Implementation Files
- `src/sagasmith/agents/oracle/skills/scene-brief-composition/SKILL.md`
- `src/sagasmith/agents/oracle/skills/content-policy-routing/SKILL.md`
- `src/sagasmith/agents/oracle/skills/player-choice-branching/SKILL.md`
- `src/sagasmith/agents/oracle/skills/inline-npc-creation/SKILL.md`
- `src/sagasmith/agents/orator/skills/scene-rendering/SKILL.md`
- `src/sagasmith/agents/archivist/skills/memory-packet-assembly/SKILL.md` — read to understand stub boundary for Phase 6

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sagasmith/schemas/narrative.py` — `SceneBrief` and `MemoryPacket` Pydantic models already fully defined with all AI-01 required fields. Phase 6 consumes these directly.
- `src/sagasmith/providers/client.py` — `invoke_with_retry` handles structured JSON calls with retry ladder (same-model repair → cheap-model repair → fail). Oracle uses this for world-bible-generation, campaign-seed-generation, and scene-brief-composition.
- `src/sagasmith/providers/openrouter.py` — `OpenRouterClient.stream()` already implemented. Orator uses this for scene-rendering.
- `src/sagasmith/providers/fake.py` — `DeterministicFakeClient` scripts per-agent responses keyed by `agent_name`. QA-05 safety tests use this.
- `src/sagasmith/services/safety.py` — `SafetyEventService.log_fallback()` is stubbed for Phase 6. The `SafetyEvent` schema already includes `"post_gate_rewrite"` and `"soft_limit_fade"` event kinds.
- `src/sagasmith/evals/redaction.py` — `RedactionCanary` pattern-match model is the basis for the keyword pre-gate implementation.
- `src/sagasmith/graph/runtime.py` — `_record_pre_narration_checkpoint()`, `resume_and_close()`, and the `snapshot.next == ("orator",)` recovery detection point. GRAPH-06/07 implementation builds here.
- `src/sagasmith/graph/bootstrap.py` — `AgentServices.llm` injection point (currently `object | None`); Phase 6 populates with real `LLMClient`.

### Established Patterns
- Agent nodes must be pure: return `dict` state updates only, no direct TUI side-effects.
- `DeterministicFakeClient` is the canonical no-paid-call test mechanism for all agent path tests.
- `pre_narration` checkpoint is written before Orator runs — deterministic outcomes locked at that point (GRAPH-07 guaranteed structurally).
- `invoke_with_retry` is the standard structured-JSON call wrapper with the 3-attempt retry ladder.
- `AgentActivationLogger` ContextVar pattern: nodes call `get_current_activation().set_skill(...)` when activation is present.
- `SchemaModel` with `extra="forbid"` for all boundary schemas; agent LLM outputs validated before state update.

### Integration Points
- `src/sagasmith/graph/graph.py` — routing edges need a new conditional: `scene_brief` present + beats not resolved → skip oracle_node. New `world_bible` and `campaign_seed` fields added to `SagaGraphState`.
- `src/sagasmith/graph/routing.py` — exhaustiveness guard must be updated when new routing branches are added.
- `src/sagasmith/agents/oracle/node.py` — stub comment says "Phase 6 replaces". Drop-in replacement site.
- `src/sagasmith/agents/orator/node.py` — stub comment says "Phase 6 replaces". Drop-in replacement site.
- `src/sagasmith/agents/rules_lawyer/node.py` — Phase 5 wired deterministic services. Phase 6 adds LLM intent-to-proposal layer upstream of existing deterministic calls.
- TUI Textual shell — reads `pending_narration` from completed graph state and appends to NarrationArea; no change to streaming delivery contract in Phase 6.

</code_context>

<specifics>
## Specific Ideas

- World bible and campaign seed run once at campaign start as real LLM calls using onboarding outputs — not canned fixtures. This is the player's first meaningful AI interaction.
- Safety post-gate uses the cheap LLM classifier (cheap_model in config) — keeps per-turn cost bounded.
- Oracle scenes span multiple player turns — a `SceneBrief` covers a whole narrative scene, not a single exchange. This is the primary cost-control lever for Oracle.

</specifics>

<deferred>
## Deferred Ideas

- Full Archivist memory assembly (AI-11) — Phase 7. Phase 6 uses a minimal stub MemoryPacket.
- Vault writes for WorldBible, CampaignSeed, vault page upserts — Phase 7.
- Real-time streaming token delivery to TUI widget — future phase after core loop is stable.
- WorldBible and CampaignSeed vault persistence — Phase 7.
- Callback ledger, callback seeding, callback payoff selection — Phase 7 (Archivist owns these).
- encounter-request-composition, pacing-calibration, canon-conflict-response Oracle skills — Phase 7 or later.
- Director Mode (player override of Oracle scene plans) — EXPX-04, post-MVP per WISHLIST.md.

</deferred>

---

*Phase: 06-ai-gm-story-loop*
*Context gathered: 2026-04-28*
