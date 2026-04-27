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
is None or stale.

## Procedure
(Phase 6 implementation.) LLM synthesizes a SceneBrief using MemoryPacket,
content_policy, and player_profile. Strict output format per oracle-skills.md §2.3.

## Failure Handling
If the LLM response fails schema validation, retry once; on second failure,
route to safety-redline-check and surface a safe fallback SceneBrief.
