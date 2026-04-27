---
name: degree-of-success
description: Compute PF2e degree of success (critical success, success, failure, critical failure) from natural roll, total, and DC.
allowed_agents: [rules_lawyer]
implementation_surface: deterministic
first_slice: true
success_signal: Every check result has a correct degree per PF2e rules including natural 1/20 step adjustment.
---
# Degree of Success

## When to Activate
After any check roll is resolved by seeded-roll-resolution.

## Procedure
Pass `natural`, `total`, `dc` to the deterministic handler.

## Deterministic Handler
Module: `sagasmith.services.pf2e`.
Function: `compute_degree(natural: int, total: int, dc: int) -> Literal["critical_success","success","failure","critical_failure"]`.

## Failure Handling
Illegal inputs (non-integer natural outside 1-20) raise ValueError — DO NOT coerce.
