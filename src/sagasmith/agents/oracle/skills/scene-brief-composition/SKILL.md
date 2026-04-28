---
name: scene-brief-composition
description: Build a structured SceneBrief for the next playable scene based on campaign state, memory packet, and player preferences.
allowed_agents: [oracle]
implementation_surface: prompted
first_slice: true
success_signal: Every brief includes required fields and never contains player-facing narration.
---
# Scene Brief Composition

## When to Activate
At the start of every turn where `state.phase == "play"` and `state.scene_brief`
is None, all `scene_brief.beat_ids` appear in `state.resolved_beat_ids`, or
player-choice-branching detects a bypass/rejection of the active scene.

## Inputs
- `MemoryPacket` with bounded recent campaign context.
- `ContentPolicy` after content-policy-routing pre-gate.
- `PlayerProfile`, plus optional `WorldBible`, `CampaignSeed`, and prior `SceneBrief`.
- Latest `pending_player_input` and a planning `scene_intent`.

## Output
- A valid `SceneBrief` object with readable `beats` and parallel stable `beat_ids`.
- Planning-only notes; no second-person/player-facing narration.

## Procedure
Use `sagasmith.prompts.oracle.scene_brief_composition` (D-06.5) and call the
configured LLM through `invoke_with_retry` with structured JSON output. Include
memory, safety, player preferences, world/campaign context, and any bypass-derived
intent. Validate the response against `SceneBrief` before it enters graph state.
Never ask the LLM to author PF2e math; mechanical triggers are requests only.

## Failure Handling
Schema failures use `invoke_with_retry`. `BudgetStopError` is handled by Oracle:
return the prior scene brief unchanged and post a `BUDGET_STOP` interrupt. If no
LLM client is configured, use the deterministic first-slice fallback brief so
no-paid-call smoke flows continue.
