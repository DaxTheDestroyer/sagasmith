---
name: content-policy-routing
description: Route proposed scene elements through content_policy rules; reshape or reject content that conflicts with player lines.
allowed_agents: [oracle]
implementation_surface: hybrid
first_slice: true
success_signal: Redlined fixture intents are rerouted before Orator sees them.
---
# Content Policy Routing

## When to Activate
Before finalizing a scene brief or beat that may touch hard or soft content limits.

## Procedure
Evaluate `scene_intent` against `ContentPolicy` before scene-brief-composition.
Use deterministic keyword/pattern matching based on the RedactionCanary model:
hard limits return `Allowed`, `Rerouted(new_intent)`, or `Blocked(reason)` per
D-06.3; soft limits are adjusted or surfaced as content warnings for downstream
post-gate work without duplicating Task 7's full safety service.

## Inputs
- `scene_intent`
- `ContentPolicy.hard_limits`
- `ContentPolicy.soft_limits`

## Output
- `Allowed` intent, rerouted safe intent, or blocked routing result.

## Failure Handling
If policy rules are ambiguous, default to the more restrictive interpretation.
Log the reroute decision for audit.
