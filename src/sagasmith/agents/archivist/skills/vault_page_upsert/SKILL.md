---
name: vault-page-upsert
description: Atomically create or update a master vault page with complete frontmatter fields. Handles slug collisions deterministically.
allowed_agents: [archivist]
implementation_surface: deterministic
first_slice: true
success_signal: Page written atomically; frontmatter validates against schema; slug collisions resolved with _N suffixes.
---

# Vault Page Upsert

## When to Activate
At turn-close for each new or updated entity discovered during the turn. Also for meta pages (world_bible, campaign_seed, rolling_summary) on first write.

## Procedure
1. Receive `entity_draft: dict` and `visibility: str` from the Archivist node.
2. Determine page type from `draft["type"]` (e.g., "npc", "location", "faction", "item", "quest", "callback", "session", "lore").
3. Build frontmatter:
   - `id`: slugify(name) with type prefix if required
   - `name`: from draft
   - `type`: constant from page type
   - `visibility`: provided (defaults to 'gm_only' unless node decides otherwise)
   - `first_encountered`: session number from state
   - All other required fields populated with empty strings, empty lists, or sensible defaults per the frontmatter schema.
4. Validate frontmatter via Pydantic; on error raise ValueError, no file written.
5. Create `VaultPage(frontmatter, body="")`.
6. Compute target path: `master_vault/<type_subfolder>/<slug>.md` using vault_service path helpers.
7. Ensure parent directory exists.
8. If file at target path already exists, try `slug_2.md`, `slug_3.md`, etc. until a free name is found.
9. Call `vault_service.atomic_write(page, target_path)`.
10. Return `(str(target_path), "created")` for new page or `(str(existing_path), "updated")` if updating existing (when draft has explicit id conflict resolution).

## Inputs
- `entity_draft: dict` — Raw entity fields from the scene/LLM output. Must include at least `name` and `type`.
- `visibility: str` — One of `"player_known"`, `"foreshadowed"`, `"gm_only"`. Node decides based on scene context.
- `session_number: int` — Current session number for `first_encountered` tracking.

## Outputs
- `(vault_path: str, action: str)` — The absolute path written and either `"created"` or `"updated"`.

## Notes
- Atomic write guarantees: temp file + fsync + os.replace + post-write validation.
- Slug collisions append a numeric suffix starting at `_2` (VAULT_SCHEMA §4.3).
- The vault service's EntityResolver index is refreshed by the caller after writes complete.
