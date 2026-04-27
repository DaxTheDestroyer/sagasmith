---
name: skill-check-resolution
description: Resolve a skill or perception check against a fixed DC by composing seeded-roll-resolution and degree-of-success.
allowed_agents: [rules_lawyer]
implementation_surface: deterministic
first_slice: true
success_signal: Fixture checks produce expected totals, degrees, and roll log entries.
---
# Skill Check Resolution

## When to Activate
When a player declares a skill or perception check (e.g., "roll perception").

## Procedure
1. Resolve the d20 roll via `DiceService.roll_d20`.
2. Compute the degree via `compute_degree` using the natural, total, and DC.
3. Build a `CheckResult` with proposal_id, roll_result, degree, effects, and state_deltas.

## Deterministic Handler
Composes:
- `sagasmith.services.dice.DiceService.roll_d20`
- `sagasmith.services.pf2e.compute_degree`

See rules-lawyer-skills.md §2.3 for full contract.

## Failure Handling
If the character sheet lacks the requested skill, return a CheckResult with
degree "failure" and an empty effect list. Do not crash the turn.
