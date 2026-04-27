---
name: seeded-roll-resolution
description: Resolve all die rolls through DiceService with replayable seeds and complete roll log entries.
allowed_agents: [rules_lawyer]
implementation_surface: deterministic
first_slice: true
success_signal: Same seed and same ordered inputs reproduce exact results.
---
# Seeded Roll Resolution

## When to Activate
Whenever a mechanical check, strike, initiative roll, or other die roll is required.

## Procedure
Build a roll request with purpose, actor_id, modifier, and roll_index.
Invoke the deterministic handler. Store the returned RollResult.

## Deterministic Handler
Module: `sagasmith.services.dice`.
Class: `DiceService`.
Method: `roll_d20(purpose, actor_id, modifier, roll_index, dc=None) -> RollResult`.

## Failure Handling
Invalid die expressions raise ValueError. Invalid seeds produce deterministic
but unexpected results — validate seed format at session start.
