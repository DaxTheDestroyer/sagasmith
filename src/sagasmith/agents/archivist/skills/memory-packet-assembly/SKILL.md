---
name: memory-packet-assembly
description: Assemble a token-bounded MemoryPacket for Oracle and Orator from scene context, player input, and retrieval layers.
allowed_agents: [archivist]
implementation_surface: hybrid
first_slice: false
success_signal: On a 50-turn fixture, packet size never exceeds the cap and an NPC introduced early is retrieved correctly when reintroduced later.
---
# Memory Packet Assembly

## When to Activate
At the start of every turn where Oracle or Orator needs contextual memory.

## Procedure
(Phase 7 implementation.) Query SQLite FTS5, LanceDB, NetworkX, and rolling
summaries. Rank and bound results into a MemoryPacket per archivist-skills.md §2.1.

## Failure Handling
If retrieval layers are unavailable, fall back to recent transcript entries
and log a degradation warning.
