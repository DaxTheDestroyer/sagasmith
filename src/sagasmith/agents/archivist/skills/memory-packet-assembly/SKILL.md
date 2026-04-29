---
name: memory-packet-assembly
description: Assemble a token-bounded MemoryPacket for Oracle and Orator from vault FTS5 search, NetworkX graph neighborhoods, rolling summary, and recent transcript context.
allowed_agents: [archivist]
implementation_surface: hybrid
first_slice: true
success_signal: Packet size never exceeds the configured cap; retrieval pulls from FTS5, NetworkX graph, callbacks, summary, and recent transcript.
---
# Memory Packet Assembly

## When to Activate
At the start of every turn where Oracle or Orator needs contextual memory.

## Procedure
1. Read the current scene context from graph state: scene id, location,
   present entities, pending player input, and pending narration.
2. Build the rolling summary from `state["rolling_summary"]` (produced by
   rolling-summary-update at scene close; empty string if no scene has
   closed yet).
3. Resolve present entities from `SceneBrief.present_entities` using the
   vault service's EntityResolver. Each resolved entity yields a
   `MemoryEntityRef` with vault_path. Unresolved names create provisional refs.
4. Query FTS5 for keyword matches against the current scene location and
   present entity names. Collect up to 5 matching vault pages.
5. Query the NetworkX graph for 1-hop neighbors of each resolved entity
   (up to 10 total neighbor IDs). Collect their vault page IDs for context.
6. Query vault for all `Callback` pages with `status='open'` where the
   callback's `seeded_in` session is ≤ current session. Include up to 3
   open callbacks.
7. Gather recent transcript entries from SQLite (last 8 entries).
8. Assemble the packet: summary, entities (resolved + graph neighbors),
   recent_turns, open_callbacks, retrieval_notes describing sources used.
9. Enforce token_cap via estimate_tokens. Truncation priority:
   recent_turns (drop oldest first) → summary (truncate tail).
10. Return a valid MemoryPacket.

## Inputs
- Current graph state, including `campaign_id`, `session_state`, `scene_brief`,
  `pending_player_input`, `pending_narration`, `rolling_summary`.
- Vault service (EntityResolver) for entity resolution.
- SQLite connection for transcript entries and FTS5 queries.
- NetworkX graph for neighbor retrieval.
- Token cap, defaulting to 2048 for Phase 7.

## Outputs
- `MemoryPacket` whose estimated `summary + recent_turns` tokens are less than
  or equal to `token_cap`.
- Vault-backed `MemoryEntityRef` values with vault_path for resolved entities;
  provisional refs for unresolved names.

## Failure Handling
If retrieval layers are unavailable, fall back to recent transcript entries
and log a degradation warning.
If SQLite itself is unavailable, fall back to current graph-state input and
pending narration.
