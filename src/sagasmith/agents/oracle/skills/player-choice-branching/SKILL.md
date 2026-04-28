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
Analyze `player_input` against the prior `SceneBrief` and `MemoryPacket`. Detect
explicit bypass/rejection markers (leave, ignore, refuse, instead, avoid, skip)
without forcing the original beat. Emit a `BranchingDecision` with kind
`continue`, `bypass`, `reject`, or `reframe`; bypass/reject/reframe produces a
revised planning intent for scene-brief-composition.

## Inputs
- `player_input`
- `prior_scene_brief`
- `memory_packet`

## Output
- `BranchingDecision` with `bypass_detected`, optional `revised_intent`, and an
  audit reason.

## Failure Handling
If the branch request is ambiguous, emit a clarification brief instead of
fabricating a player choice.
