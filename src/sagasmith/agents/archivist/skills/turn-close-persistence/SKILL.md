---
name: turn-close-persistence
description: Atomically persist turn records, roll logs, provider logs, state deltas, cost logs, and checkpoint refs within a single SQLite transaction.
allowed_agents: [archivist]
implementation_surface: deterministic
first_slice: true
success_signal: turn_records.status transitions to "complete" only after COMMIT; all related rows share the same turn_id.
---
# Turn Close Persistence

## When to Activate
At archivist completion of every play turn.

## Procedure
Build a TurnCloseBundle; invoke the deterministic handler. Plan 04-02's
GraphRuntime owns the actual invocation to keep nodes thin.

## Deterministic Handler
Module: `sagasmith.persistence.turn_close`.
Function: `close_turn(conn, bundle)`.

## Failure Handling
Any exception inside the transaction rolls back all writes; turn_records.status
remains "open". No partial persistence.
