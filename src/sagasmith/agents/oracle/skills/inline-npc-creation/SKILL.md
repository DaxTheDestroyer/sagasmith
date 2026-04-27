---
name: inline-npc-creation
description: Create a minimally-specified NPC inline when the scene demands one, respecting canon and locale conventions.
allowed_agents: [oracle]
implementation_surface: prompted
first_slice: true
success_signal: NPC drafts include name, role, voice, disposition, and safe secret handling; duplicate NPC names are resolved instead of recreated.
---
# Inline NPC Creation

## When to Activate
When a scene brief needs an NPC that does not yet exist in canon.

## Procedure
Draft a minimal NPC using scene_need, world_context, and content_policy.
Submit to Archivist entity-resolution before treating the NPC as canonical.
See oracle-skills.md §2.7.

## Failure Handling
If Archivist reports a duplicate name, merge with the existing entity page
rather than creating a second entry.
