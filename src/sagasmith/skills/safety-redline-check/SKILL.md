---
name: safety-redline-check
description: Scan any player-visible or persisted payload for secret-shaped redline content before emission or write.
allowed_agents: ["*"]
implementation_surface: deterministic
first_slice: true
success_signal: No payload containing redline patterns reaches the player or the database.
---
# Safety Redline Check

## When to Activate
Before any write to campaign files, vaults, transcripts, checkpoints, safety
events, or agent-skill-log rows. Also before any narration emission.

## Procedure
Call `RedactionCanary().scan(payload_as_string)`. A return of True means
redline content is present — reject the payload.

## Deterministic Handler
Module: `sagasmith.evals.redaction`.
Function: `RedactionCanary.scan`.

## Failure Handling
Raise `TrustServiceError("redlined content detected")` without echoing the
offending payload into logs or error messages.
