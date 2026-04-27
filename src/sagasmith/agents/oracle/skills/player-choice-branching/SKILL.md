---
name: player-choice-branching
description: Plan 2-3 branching affordances for the next player beat aligned with scene intent.
allowed_agents: [oracle]
implementation_surface: prompted
first_slice: true
success_signal: Bypass fixtures produce coherent replans without forcing the original beat.
---
# Player Choice Branching

## When to Activate
When the player accepts, rejects, bypasses, or reframes a planned beat.

## Procedure
Synthesize revised scene intent or next brief request using player_input,
prior_scene_brief, and memory_packet. See oracle-skills.md §2.4 for output
format and edge-case handling.

## Failure Handling
If the branch request is ambiguous, emit a clarification brief instead of
fabricating a player choice.
