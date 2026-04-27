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
Evaluate scene_intent against ContentPolicy. If any element violates a hard
limit, reshape or reject it. If a soft limit is approached, flag for Orator
safety post-gate. See oracle-skills.md §2.9.

## Failure Handling
If policy rules are ambiguous, default to the more restrictive interpretation.
Log the reroute decision for audit.
