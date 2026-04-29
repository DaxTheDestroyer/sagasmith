---
name: entity-resolution
description: Resolve a named entity to its canonical vault page using slug and alias lookup. Returns the page if found or signals that a new page should be created.
allowed_agents: [archivist]
implementation_surface: deterministic
first_slice: true
success_signal: Entity is found in ≥95% of correctly-named fixture cases; unknown names return None deterministically.
---

# Entity Resolution

## When to Activate
At turn-close, before writing any entity-related vault pages. Also during memory-packet assembly to canonicalize entity references.

## Procedure
1. Receive a raw entity name and optional entity type filter (npc, location, etc.).
2. Ask the vault service's EntityResolver to `resolve(name, entity_type)`.
3. If a page is returned, emit a decision: `"matched"` and pass the page forward.
4. If no page is returned, emit `"create_new"`; the Archivist will create a fresh page.

## Inputs
- `name`: str — the entity name as mentioned in narration or declared by Oracle.
- `entity_type`: str | None — optional type hint (e.g., "npc").

## Outputs
- tuple(VaultPage | None, str) — (page, "matched") or (None, "create_new").

## Notes
- Resolution uses the deterministic slug+alias index; no LLM cost.
- The resolver index is built once at service startup and refreshed after vault writes.
