---
name: scene-rendering
description: First-slice narrative rendering for completed mechanical resolutions; respects dice UX visibility and never contradicts resolved degree-of-success.
allowed_agents: [orator]
implementation_surface: prompted
first_slice: true
success_signal: Every narration line is player-facing, consistent with mechanics, and respects content policy.
---
# Scene Rendering

## When to Activate
After RulesLawyer has resolved all mechanical checks for the current beat and
the graph has resumed past the orator interrupt.

## Procedure
(Phase 6 implementation.) LLM streams narration using scene_brief, check_results,
and player preferences. DiceService results are rendered per dice UX settings.

## Failure Handling
If LLM response fails schema validation or safety post-gate, emit a safe
fallback narration line and log the event.
