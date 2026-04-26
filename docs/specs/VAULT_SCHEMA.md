# Campaign Vault Schema

**Status:** Draft
**Audience:** Implementers of the ArchivistAgent and the campaign storage
layer. Companion to `GAME_SPEC.md`.
**Pattern credit:** Karpathy LLM-Wiki pattern
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
adapted for SagaSmith's two-vault, spoiler-safe model.

---

## 1. Overview

The campaign knowledge graph is stored as a directory of Obsidian-compatible
markdown files (the **vault**). There is no separate graph database in the
MVP. The vault is the source of truth; all other read layers (NetworkX graph,
SQLite FTS5, LanceDB embeddings) are derived indices rebuilt from it.

### 1.1 Design principles

- **File-system first.** The vault is a folder of plain text files. It
  survives the app, survives OS upgrades, and requires no server.
- **Obsidian-compatible.** Every vault file is valid Obsidian markdown.
  YAML frontmatter, `[[wikilinks]]`, and `#tags` follow Obsidian conventions.
  No Obsidian-specific extensions are required to read the files as text.
- **Human-readable filenames.** Slugs are derived from canonical names
  (`npc_marcus_innkeeper.md`), not UUIDs. The vault is browsable without an
  app.
- **Two vaults, one source of truth.** The Archivist writes to the master
  vault; a sync step projects discovered content into the player vault after
  every turn. Players never have access to the master vault during an active
  campaign.
- **Git-friendly.** Every page is a text file. Version history, diffing, and
  campaign backups work with `git` automatically.

---

## 2. Two-vault architecture

### 2.1 Master vault

**Location:** `~/.ttrpg/vault/<campaign_id>/`  
(Windows: `%APPDATA%\ttrpg\vault\<campaign_id>\`)

The Archivist owns this vault entirely. It contains:
- Complete canon, including GM-only secrets.
- Open callbacks the player hasn't triggered yet.
- Oracle's planned but unplayed plot threads.
- NPC secrets, hidden agendas, unrevealed faction allegiances.
- Future encounter seeds.

The player must not be pointed at this directory. It lives inside the app's
data directory, not in the user's documents.

### 2.2 Player vault

**Location:** `<campaign_dir>/` (user-chosen on `ttrpg init`, defaults to
`~/Documents/SagaSmith/<campaign_name>/`)

This is the vault the player opens in Obsidian. It contains only content the
player character has discovered in-play, with all GM-only material stripped.
After a campaign ends, the player may run `ttrpg vault unlock` to copy the
full master vault here as a "director's cut."

### 2.3 Sync contract

The sync step runs automatically at the end of every turn (after state
checkpoint, before prompt returns). It:

1. Iterates every page in the master vault.
2. Skips pages where `visibility: gm_only` — they are never projected.
3. For pages where `visibility: foreshadowed` — writes a minimal stub to
   the player vault (name and type only; no body, no secret fields).
4. For pages where `visibility: player_known` — writes the full page to the
   player vault with GM-only content stripped (see §4.4).
5. Writes are atomic: tempfile + `os.replace()`. Obsidian auto-reloads.
6. After sync, regenerates `index.md` and appends to `log.md` in the player
   vault.

The player vault is always a **read-only artifact from the player's
perspective**. Changes the player makes to vault files are not canonical.
Canon changes go through in-game commands (`/retcon`, `/note`).

---

## 3. Folder structure

Both vaults share the same folder layout. The player vault is a filtered
subset.

```
<vault_root>/
│
├── index.md                   # Auto-generated world overview (regenerated each sync)
├── log.md                     # Append-only chronological event log
│
├── sessions/
│   ├── session_001.md
│   ├── session_002.md
│   └── ...
│
├── npcs/
│   ├── npc_marcus_innkeeper.md
│   └── ...
│
├── locations/
│   ├── loc_bent_copper_tavern.md
│   └── ...
│
├── factions/
│   ├── fac_riverboat_guild.md
│   └── ...
│
├── items/
│   ├── item_crude_map.md
│   └── ...
│
├── quests/
│   ├── quest_missing_merchant.md
│   └── ...
│
├── callbacks/
│   ├── cb_missing_merchant_witness.md
│   └── ...
│
├── lore/
│   └── (world-building, history, cosmology entries)
│
└── meta/                      # Master vault only; never projected
    ├── world_bible.md
    ├── campaign_seed.md
    └── player_profile_summary.md
```

---

## 4. Filename conventions

### 4.1 Slug rules

1. Take the canonical name (the `name` frontmatter field).
2. Lowercase.
3. Replace spaces and hyphens with `_`.
4. Remove all non-alphanumeric characters except `_`.
5. Prefix with the type code (see §4.2).
6. If the result collides with an existing file, append `_2`, `_3`, etc.

Examples:

| Canonical name | Filename |
|---|---|
| Marcus (innkeeper) | `npc_marcus_innkeeper.md` |
| Bent Copper Tavern | `loc_bent_copper_tavern.md` |
| Riverboat Guild | `fac_riverboat_guild.md` |
| Crude Map to the Mill | `item_crude_map_to_the_mill.md` |
| The Missing Merchant | `quest_missing_merchant.md` |

### 4.2 Type prefixes

| Type | Prefix | Folder |
|---|---|---|
| NPC | `npc_` | `npcs/` |
| Player Character | `pc_` | `npcs/` |
| Location | `loc_` | `locations/` |
| Faction | `fac_` | `factions/` |
| Item | `item_` | `items/` |
| Quest | `quest_` | `quests/` |
| Callback | `cb_` | `callbacks/` |
| Session | `session_` | `sessions/` |
| Lore entry | `lore_` | `lore/` |

### 4.3 Wikilink conventions

- Always link by filename without extension: `[[npc_marcus_innkeeper]]`.
- Use Obsidian's display-text syntax in prose: `[[npc_marcus_innkeeper|Marcus]]`.
- The Archivist always writes display-text wikilinks in body sections.
- Frontmatter list fields reference bare filenames without the `.md` extension
  (Obsidian resolves these correctly).

### 4.4 GM-only content stripping

The sync step strips the following before writing to the player vault:

- Any frontmatter field named `secrets`, `gm_notes`, or prefixed with `gm_`.
- Any inline block between `<!-- gm:` and `-->`. This convention lets the
  Archivist annotate body prose with hidden context.
- Any page with `visibility: gm_only` (the entire file is excluded).
- For `visibility: foreshadowed` pages, only `id`, `type`, `name`, and
  `aliases` frontmatter fields are written; the body is replaced with a
  one-line stub: `*Unknown — you have heard this name but know little more.*`

---

## 5. Page type schemas

All pages use YAML frontmatter delimited by `---`. Fields marked **(GM)**
are stripped from the player vault during sync. Fields marked **(required)**
must be present for entity resolution to work.

### 5.1 NPC (`npcs/npc_*.md`)

```yaml
---
id: npc_marcus_innkeeper          # (required) matches filename without .md
type: npc                         # (required)
name: Marcus                      # (required) canonical display name
aliases:                          # alternate names / pronouns used in prose
  - The Innkeeper
  - Marcus the innkeeper
species: Human
role: Innkeeper of the Bent Copper
status: alive                     # alive | dead | unknown | missing
disposition_to_pc: friendly       # hostile | unfriendly | neutral | friendly | allied
voice: "weary, dry humor, uses sailing metaphors"
location_current: loc_bent_copper_tavern
factions: []                      # list of fac_* IDs
first_encountered: session_001
visibility: player_known          # player_known | foreshadowed | gm_only
secrets:                          # (GM) never projected
  - "Owes a debt to the riverboat guild"
gm_notes: ""                      # (GM) never projected
---

Marcus runs the Bent Copper with characteristic weariness.
<!-- gm: Marcus will betray the PC under guild pressure. He doesn't know the missing merchant is a guild informant. -->

*Disposition:* [[npc_marcus_innkeeper|Marcus]] is [[friendly]] toward the PC.
```

### 5.2 Location (`locations/loc_*.md`)

```yaml
---
id: loc_bent_copper_tavern        # (required)
type: location                    # (required)
name: Bent Copper Tavern          # (required)
aliases:
  - The Bent Copper
  - the tavern
settlement: Rivermouth
region: The Reach
connects_to:                      # loc_* IDs for travel graph edges
  - loc_rivermouth_docks
  - loc_rivermouth_market
terrain_tags: [settlement, tavern, interior]
status: active                    # active | destroyed | abandoned | unknown
first_visited: session_001
visibility: player_known
gm_notes: ""                      # (GM)
---

A low-ceilinged tavern that smells of river mud and frying fish.
```

### 5.3 Faction (`factions/fac_*.md`)

```yaml
---
id: fac_riverboat_guild           # (required)
type: faction                     # (required)
name: Riverboat Guild             # (required)
aliases:
  - The Guild
  - the riverboat guild
alignment: neutral
disposition_to_pc: neutral
power_level: regional             # local | regional | national | world
known_members:                    # npc_* IDs visible to the player
  - npc_marcus_innkeeper
first_encountered: session_001
visibility: foreshadowed
gm_notes: ""                      # (GM)
secrets:                          # (GM)
  - "Controls the missing-merchant investigation from the shadows"
---

A powerful trade guild that controls river freight across the Reach.
```

### 5.4 Item (`items/item_*.md`)

```yaml
---
id: item_crude_map                # (required)
type: item                        # (required)
name: Crude Map                   # (required)
aliases:
  - Sera's map
  - the map
rarity: common
held_by: pc                       # pc | npc_* ID | location | lost
given_by: npc_worried_wife_sera
given_in: session_001
pf2e_ref: null                    # optional PF2e item reference
visibility: player_known
gm_notes: ""                      # (GM)
---

A hand-drawn map marking the road where Sera last saw her husband.
The markings are shaky. The mill is circled twice.
```

### 5.5 Quest (`quests/quest_*.md`)

```yaml
---
id: quest_missing_merchant        # (required)
type: quest                       # (required)
name: The Missing Merchant        # (required)
aliases:
  - find the merchant
  - Sera's job
status: active                    # active | completed_success | completed_failure | dormant | abandoned
given_by: npc_worried_wife_sera
session_opened: session_001
session_closed: null
callbacks:
  - cb_missing_merchant_witness
related_entities:
  - npc_worried_wife_sera
  - loc_rivermouth_mill
visibility: player_known
gm_notes: ""                      # (GM)
secrets:                          # (GM)
  - "The merchant is a guild informant. Solving this quest will make the guild hostile."
---

Sera, the missing merchant's wife, has asked the PC to find her husband Dav,
last seen on the road to the mill two nights ago.

**Reward:** 5 gp + a favor.

**Known leads:**
- [[item_crude_map|Crude map]] provided by [[npc_worried_wife_sera|Sera]].
```

### 5.6 Callback (`callbacks/cb_*.md`)

Callbacks are primarily GM-facing. They are always `gm_only` until paid off.
When `status: paid_off`, they are projected to the player vault as a
narrative note.

```yaml
---
id: cb_missing_merchant_witness   # (required)
type: callback                    # (required)
name: Missing Merchant Witness    # (required)
status: open                      # open | paid_off | abandoned
seeded_in: session_001
paid_off_in: null
seeded_by: oracle
related_quest: quest_missing_merchant
visibility: gm_only               # always gm_only until paid_off; then player_known
---

A dockworker witnessed the merchant being escorted off the road by two
hooded figures. Has not come forward. Can be found at the docks in sessions
2–4 if the PC investigates.
```

### 5.7 Session (`sessions/session_NNN.md`)

Session pages are added to the player vault at the **end** of the session
(not mid-session, to avoid spoiling the current scene).

```yaml
---
id: session_001                          # (required)
type: session                            # (required)
number: 1                                # integer
date_real: 2026-04-26                    # ISO date
date_in_game: "12th day of Harvest Moon, Year 423"
location_start: loc_bent_copper_tavern
location_end: loc_bent_copper_tavern
npcs_encountered:
  - npc_marcus_innkeeper
  - npc_worried_wife_sera
quests_opened:
  - quest_missing_merchant
quests_closed: []
callbacks_seeded:
  - cb_missing_merchant_witness
callbacks_paid_off: []
visibility: player_known
---

## Summary

The PC arrived in Rivermouth and took a room at the [[loc_bent_copper_tavern|Bent Copper]].
[[npc_worried_wife_sera|Sera]] approached with a desperate plea: her husband
[[npc_dav_merchant|Dav]] has been missing for two nights.

The PC accepted the job and received a crude map marking Dav's last known road.

## Beats

1. Arrived at Rivermouth docks; overheard dock gossip about strange figures on
   the south road.
2. Met [[npc_marcus_innkeeper|Marcus]]; secured lodging.
3. Sera approached at supper; described Dav's disappearance.
4. PC accepted the [[quest_missing_merchant|Missing Merchant]] quest.

## Rolls

| Roll | Mod | DC | Result |
|---|---|---|---|
| Perception (notice Sera's distress) | +4 | 12 | Success |
```

### 5.8 `index.md`

Auto-regenerated on every sync. Not hand-edited.

```markdown
# World Overview — <Campaign Name>

*Last updated: session_001 | <date>*

## NPCs (known)
- [[npc_marcus_innkeeper|Marcus]] — Innkeeper, Rivermouth. Friendly.
- [[npc_worried_wife_sera|Sera]] — Merchant's wife. Quest giver.

## Locations (visited)
- [[loc_bent_copper_tavern|Bent Copper Tavern]] — Rivermouth. Current base.

## Active Quests
- [[quest_missing_merchant|The Missing Merchant]] — Active since session 1.

## Sessions
- [[session_001|Session 1]] — Arrival in Rivermouth; met Sera.
```

### 5.9 `log.md`

Append-only. Each entry uses a consistent prefix for grep-ability:
`## [YYYY-MM-DD] <event_type> | <title>`

```markdown
## [2026-04-26] session_end | Session 1 — Arrival in Rivermouth
## [2026-04-26] entity_new | npc_marcus_innkeeper — Marcus the Innkeeper
## [2026-04-26] entity_new | npc_worried_wife_sera — Sera
## [2026-04-26] quest_opened | quest_missing_merchant — The Missing Merchant
## [2026-04-26] callback_seeded | cb_missing_merchant_witness
```

---

## 6. Visibility states and spoiler gating

| Value | Meaning | Projected to player vault? |
|---|---|---|
| `player_known` | Player has directly encountered this entity in play | Yes, full content (GM fields stripped) |
| `foreshadowed` | Entity has been hinted at but not met/found | Yes, minimal stub (name + type only) |
| `gm_only` | Oracle-internal; player has no knowledge of this | No |

**Promoting visibility** is a one-way operation. The Archivist moves `gm_only`
→ `foreshadowed` → `player_known` based on in-game events. It never demotes.

**Example promotion:**
- Riverboat Guild starts as `gm_only`.
- When Marcus drops the name in conversation: `foreshadowed`.
- When the PC investigates and learns the guild's role: `player_known`.

---

## 7. GM-only inline content

Body text in master vault pages may contain hidden GM context using HTML
comment syntax:

```markdown
Marcus runs the Bent Copper with characteristic weariness.
<!-- gm: He will betray the PC under guild pressure. Not yet known to player. -->

He offers the PC a room for 2 sp/night.
```

The sync step strips every block matching `<!-- gm:…-->` before writing to
the player vault. The closing `-->` must be on the same or following line.
Multi-line GM blocks are supported:

```markdown
<!-- gm:
  Marcus's debt is exactly 40 gp.
  Guild contact: npc_guild_enforcer_roth (gm_only).
-->
```

**Important:** GM comments must never cross a frontmatter boundary. Keep them
in the body section only.

---

## 8. Entity resolution

Before creating a new vault page, the Archivist runs a three-step resolution
check to enforce the "one entity, one page" invariant (GAME_SPEC §3.5):

1. **Slug match.** Compute the slug of the incoming entity name. If a file
   with that slug exists, it is the same entity.
2. **Alias match.** If no slug match, search the `aliases` frontmatter field
   across all pages of the same type. Case-insensitive.
3. **Vector similarity.** If no alias match, query LanceDB with the incoming
   name + contextual description. If cosine similarity ≥ 0.92, treat as the
   same entity and propose the match to the Archivist agent for confirmation.

If all three steps return no match, a new page is created with `visibility:
gm_only` and promoted as the turn resolves.

---

## 9. Derived read layers

The vault is the source of truth. Three derived layers are built from it:

| Layer | How built | Used for |
|---|---|---|
| **NetworkX graph** | Load on startup: nodes from all pages; edges from `[[wikilinks]]` and `connects_to` / `factions` / `related_entities` frontmatter | Topology queries (NPC relationship paths, location travel graph, faction membership), callback reachability |
| **SQLite FTS5** | Index on startup + incremental update per sync | Full-text search over page bodies; used when context retrieval needs exact phrase matching |
| **LanceDB** | Embedding upsert per new/changed page | Semantic entity resolution (§8 step 3); fuzzy memory retrieval for `MemoryPacket` construction |

All three are **rebuild-safe**: if the derived layers are lost or corrupted,
running `ttrpg vault rebuild` regenerates them from the markdown files alone.

---

## 10. Obsidian setup recommendations

These are optional but improve the player experience.

### 10.1 Recommended core settings

- **Files & Links → New link format:** `Shortest path when possible`
- **Files & Links → Use `[[Wikilinks]]`:** On
- **Files & Links → Attachment folder:** `assets/` (for any images ArtistAgent
  embeds post-MVP)
- **Editor → Fold frontmatter:** On (keeps pages tidy when reading)

### 10.2 Recommended community plugins

| Plugin | Purpose |
|---|---|
| **Dataview** | Run dynamic queries over frontmatter (e.g., "all alive NPCs", "open quests") |
| **Privacy Glasses** | Optional: visually blur `#spoiler`-tagged content for streaming sessions |
| **Graph Analysis** | Enhanced graph view with community detection |

Dataview example — all known alive NPCs:
```dataview
TABLE role, disposition_to_pc, location_current
FROM "npcs"
WHERE type = "npc" AND status = "alive" AND visibility = "player_known"
SORT name ASC
```

### 10.3 Graph view tips

- Obsidian's built-in graph view shows wikilink connections. Color groups:
  - Yellow: NPCs
  - Green: Locations
  - Purple: Factions
  - Orange: Quests
- Clusters of heavily-connected nodes visualize natural factions and story
  arcs. This is the "fan wiki" view of the campaign.

---

## 11. Seed vault

**Location:** `docs/seed_vault/` in the repository root.

**Status:** Planned fixture set. This directory must exist before the first
release-candidate eval run; it is not required for the initial code scaffold.

A bundled example vault covering three fictional sessions of the sample
campaign introduced in `GAME_SPEC.md` §12. Purposes:

- Demonstrates the schema in practice without requiring LLM calls.
- Allows contributors to validate the sync step, entity resolution, and
  Obsidian compatibility against real data.
- Shipped alongside the app as the basis for the onboarding demo
  (`ttrpg demo`).

The seed vault contains both a sample master vault (`seed_vault/master/`)
and a sample player vault (`seed_vault/player/`), so the sync step output
can be tested by diffing them.

**Seed campaign premise:** The PC has arrived in Rivermouth, accepted the
missing-merchant quest from Sera, investigated the docks, and completed
one combat encounter with guild hired-swords. Three sessions covered.

---

## 12. Campaign end — master vault unlock

When the player runs `ttrpg vault unlock` (or the equivalent end-of-campaign
command), the Archivist:

1. Copies the full master vault to the player vault location.
2. Removes the `<!-- gm:` comment stripping and `gm_*` field stripping.
3. Generates an **epilogue page** (`meta/epilogue.md`) summarizing:
   - Every open callback and whether it was triggered.
   - Every faction's final disposition to the PC.
   - Every NPC's final status.
   - The arc the Oracle had planned vs. what actually happened.
4. Updates `index.md` to include all previously hidden entities.

The unlocked vault is a self-contained, permanent artifact of the campaign.
It can be shared, committed to git, or opened in Obsidian as a complete
fan-wiki of the story.

---

## 13. Documents cross-referencing this spec

- `docs/specs/GAME_SPEC.md` §3.5 — ArchivistAgent behavior and acceptance
  criteria (refers to this document for storage architecture detail).
- `docs/WISHLIST.md` §5.1 — Richer graph queries as a future option if
  NetworkX hits limits; Kuzu named as candidate.
- `docs/specs/agents/archivist-skills.md` — Archivist capability catalog
  references the page types and storage contracts defined here.
