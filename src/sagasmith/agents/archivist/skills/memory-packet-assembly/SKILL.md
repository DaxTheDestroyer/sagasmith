---
name: memory-packet-assembly
description: Assemble a token-bounded Phase 6 MemoryPacket stub for Oracle and Orator from scene context and recent transcript rows.
allowed_agents: [archivist]
implementation_surface: hybrid
first_slice: true
success_signal: Packet size never exceeds the configured cap and recent transcript context is available when SQLite rows exist.
---
# Memory Packet Assembly

## When to Activate
At the start of every turn where Oracle or Orator needs contextual memory.

## Procedure
Phase 6 uses a deterministic stub only; full retrieval is deferred to Phase 7.

1. Read the current scene context from graph state: scene id, location,
   present entities, pending player input, and pending narration.
2. Query SQLite for the most recent transcript entries for the campaign,
   joining `turn_records` to `transcript_entries` and ordering by completed
   turn time plus transcript sequence.
3. Format those entries as compact `turn_id:sequence:kind: content` lines for
   `MemoryPacket.recent_turns`.
4. Create provisional entity references for the active location, present scene
   entities, and obvious capitalized names in recent transcript context. Entity
   ids use stable lowercase slug format: `{kind}_{name_slug}`.
5. Construct a short summary describing turn count, scene intent/location when
   known, and whether recent transcript context was found.
6. Enforce the token cap with `estimate_tokens` by dropping oldest recent turns
   first, then trimming summary text if needed.
7. Return a valid `MemoryPacket` with retrieval notes that clearly mark this as
   the Phase 6 transcript-only stub.

## Inputs
- Current graph state, including `campaign_id`, `session_state`, `scene_brief`,
  `pending_player_input`, and `pending_narration`.
- SQLite connection when available from the runtime service bundle.
- Token cap, defaulting to the Phase 6 cap in the implementation module.

## Outputs
- `MemoryPacket` whose estimated `summary + recent_turns` tokens are less than
  or equal to `token_cap`.
- Provisional `MemoryEntityRef` values only; no vault writes or full canonical
  entity resolution in Phase 6.

## Failure Handling
If retrieval layers are unavailable, fall back to recent transcript entries
and log a degradation warning.
If SQLite itself is unavailable, fall back to current graph-state input and
pending narration so no paid calls or full Archivist implementation are needed.
