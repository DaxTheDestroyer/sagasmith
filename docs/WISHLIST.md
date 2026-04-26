# SagaSmith — Post-MVP Wishlist

**Status:** Backlog | **Last updated:** 2026-04-24 (VillainAgent added)

**What this is:** A reference document of features that were intentionally deferred
from the MVP (minimum viable product) during the initial design and planning of
SagaSmith. These features were either explicitly stubbed, explicitly excluded
from scope boundaries, or described in the original concept but cut for the first
playable release.

This document is **not a commitment** — it is a source of truth for future
milestone scoping, feature prioritization, and architectural roadmapping. Each
item references the MVP spec or design session where the deferral decision was
made, so context is never lost.

---

## 1. Deferred Agents

The MVP ships with three full agents stubbed out or absorbed into OracleAgent's
responsibilities (§1.1–§1.3 — these have placeholder interfaces in the MVP
codebase). A fourth agent (§1.4 VillainAgent) is fully deferred with no MVP
footprint at all.

### 1.1 ArtistAgent

**What it does:** Generates AI art on demand — NPC portraits, location
illustrations, item art, scene compositions — and feeds them to the TUI or GUI
so the player sees a visual world, not just text.

**Why it was deferred:** Image generation is expensive, requires a dedicated
pipeline (model selection, style guide, prompt engineering, caching, storage),
and the MVP's core value proposition is the narrative + memory + rules stack.
Visuals are a premium layer.

**MVP state:** `ImageProvider` interface exists. All calls return a placeholder
ASCII/text description instead of an image. The TUI has a panel slot reserved for
art but renders a placeholder box.

**What full implementation looks like:**
- Style guide system (player can define or select a visual style; e.g.,
  "16-bit pixel art," "oil painting," "ink sketch")
- Prompt pipeline that translates `SceneBrief` + `PlayerProfile` + entity refs
  into image prompts
- Consistency guard (same NPC should look similar across sessions; same
  location should not drift)
- Model routing (DALL-E, Stable Diffusion API, local diffusion, etc.)
- Asset storage and deduplication (don't regenerate the same tavern every time)
- Integration with Archivist so art is linked to vault pages (NPC portraits
  embedded in `npcs/*.md`, location art in `locations/*.md`)

**Complexity:** High. The consistency problem alone is a research project.

---

### 1.2 CartographerAgent

**What it does:** Owns spatial representation — world maps, regional maps,
dungeon maps, and battle maps. Ensures that "the inn is west of the square"
stays true across sessions and that tactical combat has real geometry.

**Why it was deferred:** The MVP uses theater-of-mind combat with abstract
position tags (`close | near | far | behind_cover`). A full spatial engine
(graph-based or grid-based) is a large subsystem and not required to prove the
narrative + rules + memory loop.

**MVP state:** OracleAgent emits textual spatial notes ("the cave entrance is
roughly 200 feet below the ridge") inside `SceneBrief`. No machine-readable
spatial graph. No map rendering.

**What full implementation looks like:**
- World graph: nodes (locations) + edges (paths) with travel time, terrain,
  danger level
- Regional maps: 2D or 2.5D representation of a region for exploration
- Dungeon maps: procedurally or AI-generated room graphs for enclosed spaces
- Battle maps: grid-based tactical combat maps with cover, elevation,
  difficult terrain
- Integration with Oracle so quests naturally route through spatial topology
- Integration with Artist so maps have visual representation
- Integration with Orator so spatial descriptions are grounded in actual
  coordinates, not hallucinated

**Complexity:** Medium-High for textual/graph maps; High for visual map
rendering + battle map tactical UI.

---

### 1.3 PuppeteerAgent

**What it does:** A standalone agent responsible for populating the world with
NPCs. It creates characters with consistent personalities, voices, backstories,
stats, and relationships; manages their schedules and goals; and drives their
behavior when the player interacts with them.

**Why it was deferred:** The MVP's world is small (levels 1–3, one region). The
Oracle can generate NPCs inline without a dedicated subsystem. A standalone
Puppeteer becomes necessary when the NPC count grows large enough that the
Oracle cannot track them all.

**MVP state:** Oracle generates NPCs inline as needed and feeds them to the
Archivist. No dedicated NPC behavior engine. NPCs are reactive, not proactive.

**What full implementation looks like:**
- NPC generation pipeline: personality, voice, backstory, secrets, stats,
  relationship web
- Proactive NPC scheduler: NPCs have daily routines, goals, and agendas;
  they move around the world graph and initiate contact with the player
- Faction system: NPCs belong to factions with goals, tensions, and plots
- NPC memory: Puppeteer maintains a separate memory layer for what each NPC
  knows, believes, and feels
- Dialogue engine: structured conversation trees or LLM-driven dialogue with
  personality constraints
- Integration with Artist for NPC portraits
- Integration with Rules Lawyer for NPC stat blocks and combat behavior

**Complexity:** High. The proactive scheduler and faction system are essentially
a second game AI layer.

---

### 1.4 VillainAgent

**What it does:** Owns the campaign's antagonists as an active, thinking
opposition. Designs their identities, motivations, schemes, and plots;
plans the moves the antagonist takes against the player between scenes;
reacts to player successes and failures; and generates the unique monsters
and encounters the villain throws at the party.

Crucially, **the VillainAgent's first motivation is a fun interactive
experience, not winning.** It is not a chess opponent trying to defeat the
player — it is a dramatic-writing partner whose job is to create memorable,
interesting villains whose conflict drives a satisfying story. A villain
that would "win" by simply ambushing the level-1 PC with overwhelming force
is the wrong answer even when mechanically valid; the right answer is the
one that creates the best scene, the best reveal, the best recurring threat.

**Why it was deferred:** OracleAgent currently owns antagonist design,
encounter composition, and plot seeding inline. A standalone adversarial
agent is a meaningful complexity add — it needs its own motivation model,
a planning loop that runs between scenes, a persistent memory of what the
villain knows about the player, and a negotiated interface with Oracle
that divides narrative authority. MVP campaigns (PF2e levels 1–3, typically
a single arc) are short enough that a persistent recurring antagonist with
evolving schemes is not required to validate the core loop.

**MVP state:** None. Antagonists are created inline by OracleAgent within
`SceneBrief` and `Encounter` records. Monsters come from curated PF2e ORC
bestiary entries — no AI-designed unique creatures. There is no villain
dossier, no scheme tracker, no between-scene adversary planning.

**What full implementation looks like:**

- **Villain dossier** — per-campaign record for each major antagonist:
  identity, origin, motivations, resources, lieutenants, known facts
  about the player, unknown-but-assumed facts, relationship web, personal
  style and voice, aesthetic signatures
- **Scheme planner** — multi-step plots the villain is actively executing,
  with beats the player can interrupt, accelerate, discover early,
  accidentally aid, or miss entirely; schemes persist across sessions and
  evolve based on player actions
- **"Fun over winning" constraint** — a decision filter that scores
  candidate villain actions by dramatic/narrative value first and tactical
  effectiveness second; prevents the agent from trivially defeating the
  player with optimal play and enforces the "memorable villain" goal
- **Unique monster generator** — takes a theme, the active rule system, and
  an encounter budget and produces novel, mechanically-valid stat blocks
  that feel like *this villain's* creatures rather than stock bestiary
  pulls (e.g., the swamp-witch's bog-drake, the lich's clockwork wraiths,
  the pirate-king's storm-bound ghost crew)
- **Encounter composer** — combines the villain's resources, chosen
  terrain, unique monsters, and tactical goals into scripted-yet-reactive
  encounters that reveal character and advance the plot
- **Coordination contracts:**
  - with OracleAgent: negotiates which scenes are villain-driven vs.
    player-driven; hands off scheme beats to Oracle for scene planning
  - with ArchivistAgent: persistent villain memory (what the villain
    learned, past setbacks, grudges)
  - with RulesLawyerAgent: stat block validation against the active
    rule system's legality rules
  - with PuppeteerAgent (if present): villain NPCs, lieutenants, and
    their day-to-day behavior
  - with ArtistAgent (if present): villain portraits and unique monster
    illustrations with consistent aesthetic signatures
- **Safety integration:** all VillainAgent output (scheme descriptions,
  monster descriptions, villain dialogue) passes through the same
  two-phase SafetyGuard as Orator output; `ContentPolicy` redlines apply
  to villain actions just as they apply to any other content

**Complexity:** High. The agent needs its own planning loop, persistent
memory, a novel content generator that respects the active rule system,
and negotiated authority with Oracle. The "fun over winning" constraint
is easy to state and hard to tune — it is essentially a creative-writing
heuristic encoded in prompts and evals, and will likely require its own
regression scenarios in the eval harness to prevent regressions.

---

## 2. Deferred Combat & Rules

### 2.1 Tactical Grid / Map-Based Combat

**Original concept:** The player onboarding asks for combat preference:
- *Theater of the mind* — Orator describes the scene, positions are abstract
- *Tactical map-based* — Cartographer generates a battle map; the player sees
  exact positions, cover, line of sight, and can make spatially precise moves

**MVP state:** Only theater-of-mind is implemented. `PlayerProfile.combat_style`
is persisted as `"theater_of_mind"` but no other value is valid.

**What full implementation looks like:**
- Battle map generation per encounter (grid or hex, with terrain features)
- TUI tactical mode: a grid panel showing PC, enemies, cover, hazards
- Mouse/keyboard interaction for movement, targeting, area-of-effect placement
- Rules Lawyer integration: cover bonuses, flanking, line of sight, difficult
  terrain all computed from map state
- Integration with Cartographer for map consistency
- Integration with Artist for visual map rendering (if Artist is implemented)

**Complexity:** High. Requires a full 2D spatial engine + UI + rules integration.

---

### 2.2 PF2e Character Levels 4+

**MVP state:** PF2e rules engine covers levels 1–3 only. This gates:
- Class feats beyond level 2
- Skill increases and skill feats
- Ancestry feats beyond level 1
- Higher-level spells and equipment
- Advanced archetypes and dedications

**What full implementation looks like:**
- Complete PF2e progression tables through level 20
- Full feat database and selection UI
- Higher-level monster bestiary
- High-level encounter math (extreme/impossible encounters)
- Epic campaign arcs designed for high-level play

**Complexity:** Medium. The engine architecture is designed to scale (engine
schema + `Protocol` interface), but the data volume is large.

---

### 2.3 Additional Rule Systems

**Original concept:** The Rules Lawyer + engine is designed behind a `Protocol`
interface so that the game is not locked to Pathfinder 2e. The player could
select a different system at campaign creation.

**MVP state:** Only PF2e is implemented. The `Protocol` abstraction exists but
has only one implementation.

**Candidate systems to support:**
- D&D 5e (largest player base)
- Pathfinder 1e / 3.5e (legacy compatibility)
- Custom / homebrew system builder
- Blades in the Dark / Forged in the Dark (narrative-first, lighter rules)
- OSR systems (Old-School Renaissance, e.g., OSE, Knave)

**Complexity:** High per system. Each requires a full rules data set, test
suite, and balance calibration.

---

### 2.4 Open / Custom Rule System Builder

**Long-term vision:** A declarative rule system format (YAML/JSON schema) that
allows players or the community to define their own TTRPG mechanics. The engine
reads the definition and enforces it deterministically.

**What this enables:** Community content, house-rule formalization, and
experimentation with new mechanics without code changes.

**Complexity:** Very High. Effectively building a rules-description language
and interpreter.

---

## 3. Deferred Visuals & UI

### 3.1 AI-Generated Art Pipeline

This is the full manifestation of ArtistAgent (see §1.1), but called out
separately because it is a major player-facing feature category.

**Art types the player would see:**
- **NPC portraits** — shown when meeting or speaking to a named character
- **Location illustrations** — shown on first arrival or when the Orator
  describes a vista
- **Item art** — shown when acquiring notable equipment or loot
- **Scene compositions** — cinematic moments (combat opening, dramatic reveals)
- **Campaign splash / title card** — shown at session start

**What makes this hard:**
- Style consistency across sessions (same NPC shouldn't look different each time)
- Content safety (art must respect the player's `ContentPolicy`)
- Cost control (image generation is more expensive than text per token)
- Latency (generating art mid-session adds wait time)
- Storage (campaigns accumulate many images)

**MVP mitigation:** Placeholder interface means the TUI panel and data model
are ready; only the generation backend is missing.

---

### 3.2 Rich Animated Dice UX

**Original concept:** When `dice_ux=reveal`, the player sees pixelated dice
rolling with animation — a tactile, satisfying moment before the result.

**MVP state:** Dice overlay shows DC, modifiers, and an animated d20 result.
This is functional but minimal — it's a UI modal, not a rich visual spectacle.

**What full implementation looks like:**
- Pixel-art or stylized dice sprites (d4, d6, d8, d10, d12, d20, d100)
- Physics-based or hand-tuned rolling animation
- Sound effects (optional)
- Multiple visual themes matching `PlayerProfile` aesthetic
- Special animations for critical successes and critical failures
- Animated dice for physical dice rollers who want the tactile feel

**Complexity:** Low-Medium. Primarily art + UI animation work, not AI or rules.

---

### 3.3 GUI Frontend (Tauri / React or Web)

**MVP state:** TUI (Textual) only. The terminal application is the only
interface.

**What a GUI would enable:**
- Mouse-driven interaction (clicking on map, inventory, character sheet)
- Richer layout (side-by-side panels, draggable windows, persistent HUD)
- Better art display (the TUI can show images in some terminals, but a GUI
  can render them natively)
- Accessibility (screen readers, scalable text, colorblind modes)
- Mobile / tablet play (web frontend)

**Candidate stacks (from original planning):**
- Tauri + React (desktop, lightweight, Rust core)
- Web frontend (any device with a browser)
- Both could share the same Python backend via a local API

**Complexity:** Medium for a basic GUI wrapper around the existing backend;
High for a deeply integrated, native-feeling RPG client.

---

## 4. Deferred Social & Multiplayer

### 4.1 Party Companions (Multi-PC)

**MVP state:** Solo player, solo PC. No companions.

**What full implementation looks like:**
- The player can create or recruit companion characters
- Companions have their own character sheets, inventory, and agency
- The Oracle treats the party as a unit for encounter design
- The player controls companions in combat or sets AI behavior modes
- Companion loyalty / relationship system (affected by player choices)
- Companion-initiated dialogue and side-quests

**Complexity:** Medium-High. Requires multi-character state management, AI
party control, and narrative branching for companion reactions.

---

### 4.2 Multiplayer / LAN Shared Campaigns

**Original concept:** Multiple players connect to a shared campaign session,
either over LAN or via a lightweight server. One player's instance acts as host;
others join as clients.

**What this enables:**
- True party-based TTRPG play with friends
- Shared world state synchronized across clients
- One player's actions affect the world for everyone
- Real-time or turn-based multiplayer input

**What makes this hard:**
- Network synchronization of the full game state (combat, memory, world graph)
- Conflict resolution when players want to do different things simultaneously
- Cost scaling (each player may bring their own LLM credentials, or the host
  bears the full cost)
- Session persistence across disconnects

**Complexity:** Very High. This is essentially building a networked game server.

---

### 4.3 Shared Campaign Seeds

**What it is:** A curated or community-generated set of "seed" campaigns
(worlds, starting scenarios, pre-generated NPCs, plot hooks) that players can
select at onboarding instead of going through the full interview.

**Why it matters:** Lowers the barrier to entry; gives players a quick start;
builds a community content ecosystem.

**Complexity:** Low for a basic seed library; Medium for a rating/curation
system and community submission pipeline.

---

## 5. Deferred Architecture & Experience Options

### 5.1 Richer Graph Queries (Optional Embedded Graph DB)

**Context:** The MVP stores the campaign knowledge graph as an Obsidian-
compatible markdown vault (see `docs/specs/VAULT_SCHEMA.md`). Topology
queries (faction membership, NPC relationship paths, travel graphs) are
served by an in-memory NetworkX graph derived from the vault's wikilinks
and frontmatter at startup. This covers every query the Archivist needs
for the MVP's supported campaign scale.

**Why richer graph queries are deferred:** At the campaign sizes the MVP
targets (hundreds of entities, one player), NetworkX + SQLite FTS5 +
LanceDB is fast and sufficient. A dedicated graph DB adds server or
library overhead that would cost more in distribution friction than it
returns in query expressiveness.

**When this would become relevant:**
- Very long campaigns with thousands of deeply interlinked entities where
  multi-hop constrained queries become slow in NetworkX.
- Director Mode (§5.2) or Multiplayer (§6.3) where concurrent read/write
  access to the graph is required.
- Advanced analytics features (community detection, centrality, narrative
  arc mapping) beyond what NetworkX handles cleanly.

**Preferred candidate if added:** Kuzu — embedded, `pip install`-able,
MIT-licensed, Cypher-compatible, single-directory storage. The
`CanonStore` adapter defined in `VAULT_SCHEMA.md` makes the vault the
source of truth; Kuzu would become a derived index layer rebuilt on
startup, not a replacement for the vault format.

**What would NOT be used:** Neo4j. Its JVM server, GPLv3 license, and
per-OS install complexity are incompatible with a `pip install` CLI tool
targeting non-technical users.

**Complexity:** Low-Medium if added. The vault is the source of truth;
the graph DB is a derived read layer. The `CanonStore` adapter boundary
means no other agent changes. Risk is Kuzu's Cypher gaps vs. the query
set at that time.

---

### 5.2 Director Mode

**What it is:** A mode where the player (or a human GM) takes direct control
of the Oracle's levers. The human can override scene briefs, force specific
plot hooks, or manually trigger encounters. The AI agents become assistants
rather than drivers.

**Use cases:**
- A human GM uses SagaSmith as a co-GM (world-building, NPC management,
  rules enforcement)
- An advanced player wants to script their own campaign and use the agents
  for narration and memory only
- Playtesting and content creation

**Complexity:** Medium. Requires a command layer that intercepts or overrides
Oracle output, plus a new UI mode.

---

### 5.3 Voice I/O

**What it is:** Speech-to-text for player input and text-to-speech for Orator
narration. The player can speak their actions and hear the story read aloud.

**Why it matters:** Accessibility (players with typing difficulties); immersion
(hearing the story in a generated voice); hands-free play.

**What full implementation looks like:**
- STT integration (Whisper API, local Whisper, or OS-native)
- TTS integration (ElevenLabs, OpenAI TTS, or OS-native)
- Voice selection per agent (Oracle's voice is different from Orator's)
- Punctuation and emotion hints in TTS prompts
- Push-to-talk or voice-activity-detection input modes

**Complexity:** Low-Medium for basic STT/TTS; High for characterful voices
and emotion rendering.

---

## 6. Long-Term Vision

These are not deferred from the MVP so much as aspirational directions the
project could grow if it succeeds.

### 6.1 Companion Mobile App

A lightweight mobile companion that lets the player:
- Review their character sheet and inventory between sessions
- Read session recaps
- Manage safety settings and content lines
- Receive "world updates" (what happened in the world while you were away)

**Complexity:** Medium. Requires a backend API and mobile client.

---

### 6.2 Community Content / Modding Platform

A platform for players to share:
- Campaign seeds and worlds
- Custom rule system definitions
- NPC packs and bestiaries
- Art style guides and prompts
- Eval scenarios and regression tests

**Complexity:** High. Requires user accounts, content moderation, version
control, and discovery features.

---

### 6.3 Persistent MMO-like Shared World

The furthest-out vision: a single persistent world server where many players'
campaigns coexist. What one player's Oracle does in the world affects the
world state for others. Factions rise and fall; NPCs age and die; the world's
history is a shared emergent narrative.

**Complexity:** Very High. This is a research project in emergent narrative
and distributed state, not a product feature.

---

## How This Document Is Maintained

1. **When a feature ships**, move it from this document into `CHANGELOG.md` and
delete it from here. Do not keep shipped items in the wishlist.
2. **When a feature is promoted to a concrete milestone**, add a reference to
the milestone number and target version in its entry.
3. **When a new deferred feature is identified** during design or planning,
add it to the appropriate category with the same structure (What / Why deferred /
MVP state / Full implementation / Complexity).
4. **Review quarterly** to re-prioritize based on player feedback, technical
maturity of dependencies, and project goals.

---

## Cross-References

| Deferred Feature | MVP Hook / Partial Implementation |
|---|---|
| ArtistAgent | `ImageProvider` interface; placeholder TUI panel |
| CartographerAgent | Textual spatial notes in `SceneBrief` |
| PuppeteerAgent | Oracle inline NPC generation; Archivist entity tracking |
| VillainAgent | None; Oracle plans antagonists inline, curated bestiary for encounters |
| Tactical combat | `PlayerProfile.combat_style` field (always `"theater_of_mind"`) |
| GUI frontend | None; TUI is the sole interface |
| Multiplayer | None; solo player assumed throughout |
| Other rule systems | `RulesEngine` `Protocol` abstraction (only PF2e impl) |
| Rich dice UX | Dice overlay modal exists; minimal animation only |
| Voice I/O | None; text-only input/output |
| Richer graph queries | `CanonStore` adapter boundary; Kuzu named as candidate; vault stays source of truth |
| Director mode | None; Oracle is always in control |

---

*Generated from the initial project design session (2026-04-22) and subsequent
planning passes. See `docs/specs/GAME_SPEC.md` §1.3 and §3.7 for the formal MVP
scope and stub definitions.*
