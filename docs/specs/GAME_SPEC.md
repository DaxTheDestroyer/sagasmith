# SagaSmith - Game Specification

**Status:** Draft. Target file: `docs/specs/GAME_SPEC.md`.
**Audience:** Implementers of the game runtime. Companion to the master
architecture plan.
**Format:** Implementation spec with acceptance criteria per component.

## 1. Overview

### 1.1 What this is

A single-player, AI-run tabletop RPG that delivers the "go anywhere, do
anything" promise of human-GM play inside a terminal application. The game
is **run** by a cooperating set of AI agents; the **player** brings their own
LLM credentials (OpenRouter or direct providers).

**Implementation contract:** Provider routing, streaming, retries, secret
storage, and cost accounting are defined in `docs/specs/LLM_PROVIDER_SPEC.md`.

### 1.2 Player value

- Persistent, multi-session campaigns without context loss.
- A game shaped by a real onboarding interview — the system adapts to the
  player's preferences, not the other way around.
- Deterministic, auditable rules (Pathfinder 2e) underneath improvised
  narrative.
- Safety-first content handling via lines, veils, and real-time player
  controls.

### 1.3 MVP scope boundaries

- Solo player, solo PC (no party companions in MVP).
- Pathfinder 2e, character levels 1–3 only.
- Theater-of-mind combat only.
- No image or map generation (placeholder interface only).
- TUI (Textual) only; no GUI.

## 2. Players and preferences

### 2.1 PlayerProfile (data record)

Persisted after onboarding. Drives every downstream system.

```json
{
  "genre": ["high_fantasy"],
  "tone": ["heroic", "hopeful", "occasional_dark"],
  "touchstones": ["Earthsea", "Disco Elysium", "Dragon Age: Origins"],
  "pillar_weights": {"combat": 0.3, "exploration": 0.3, "social": 0.3, "puzzle": 0.1},
  "pacing": "medium",
  "combat_style": "theater_of_mind",
  "dice_ux": "reveal",
  "campaign_length": "open_ended",
  "character_mode": "guided",
  "death_policy": "heroic_recovery",
  "budget": {"per_session_usd": 2.50, "hard_stop": true}
}
```

### 2.2 ContentPolicy (data record)

```json
{
  "hard_limits": ["graphic_sexual_content", "harm_to_children"],
  "soft_limits": {"graphic_violence": "fade_to_black", "torture": "fade_to_black"},
  "preferences": ["moral_ambiguity_ok", "existential_themes_ok"]
}
```

### 2.3 HouseRules (data record)

```json
{
  "dice_ux": "reveal",
  "initiative_visible": true,
  "allow_retcon": true,
  "auto_save_every_turn": true,
  "session_end_trigger": "player_command_or_budget"
}
```

**Acceptance criteria:** Onboarding produces all three records, validates
them against JSON Schema, and persists them to SQLite before any gameplay
begins.

**Implementation contract:** Concrete runtime schemas for these records and
all cross-agent state objects are defined in `docs/specs/STATE_SCHEMA.md`.

## 3. Agents as product components

Each agent is a player-facing behavior contract. Internal transport and
prompts live in the main plan (§3); this section describes observable
behavior and acceptance criteria.

### 3.1 OnboardingAgent

- **Responsibility:** Conducts a structured interview; produces
  `PlayerProfile`, `HouseRules`, `ContentPolicy`; then hands off to character
  creation.
- **Inputs:** None (first run) or existing profile (re-interview).
- **Outputs:** Three validated records in SQLite.
- **Observable behavior:**
  - Never asks the same question twice.
  - Elaborates follow-ups based on answers (e.g., "You liked Disco
    Elysium — should social encounters skew weird/absurdist?").
  - Produces a summary screen the player can edit before committing.
- **Acceptance criteria:**
  - Completes in under 15 minutes for a median player.
  - Profile records pass schema validation.
  - User can re-run onboarding from a menu without losing the campaign.

### 3.2 OracleAgent (the GM)

- **Responsibility:** World-building, campaign seeding, scene planning,
  callback tracking, encounter design.
- **Inputs:** `PlayerProfile`, `WorldBible` (if exists), current
  `SessionState`, player input, `CanonConflict` events from Archivist.
- **Outputs:** `WorldBible` (once), `CampaignSeed` (once), `SceneBrief` (per
  scene), `Encounter` (when combat triggered), callback registrations.
- **Observable behavior:**
  - Never narrates directly to the player.
  - Surfaces 3–5 plot hooks at start; expands any hook the player bites
    into a full arc with beats and success/failure branches.
  - Tracks seeded foreshadowing and prefers resolving old callbacks over
    seeding new ones when the backlog grows.
  - Re-plans on the fly when the player skips or bypasses beats.
- **Acceptance criteria:**
  - `SceneBrief` always includes `intent`, `beats`, `success_outs`,
    `failure_outs`, `present_entities`, `pacing_target`.
  - Callback ledger shows ≥ 1 seed-to-payoff cycle in any 5-session test.
  - Encounter math validates against PF2e XP budget tables.

### 3.3 OratorAgent (the only voice the player hears)

- **Responsibility:** Render `SceneBrief` + resolved mechanics + memory into
  second-person streamed prose.
- **Inputs:** `SceneBrief`, `MemoryPacket`, player input, pre-resolved
  `RollResult`s, `PlayerProfile.tone`, active `ContentPolicy`.
- **Outputs:** Streamed narration tokens; rarely, late `RollRequest` tool
  call (only at commit points).
- **Observable behavior:**
  - Prose never contradicts mechanical outcomes.
  - Respects `dice_ux` mode:
    - `auto`: weaves outcomes seamlessly.
    - `reveal`: narrates the attempt; hands off to the dice modal;
      resumes with outcome.
    - `hidden`: never names rolls, DCs, or modifiers.
  - Honors `PlayerProfile.tone` (prose register, pacing, content).
  - Fades to black on soft-limit content and redlines hard-limit content.
- **Acceptance criteria:**
  - First streamed token within 2 s p50 on a healthy connection.
  - No "dead air": every Orator turn emits at least one complete beat of
    narration.
  - Zero rules contradictions in a 50-turn regression transcript.

### 3.4 RulesLawyerAgent

- **Responsibility:** Translate player intent into mechanical checks; run
  deterministic PF2e resolution; apply effects.
- **Inputs:** `SituationCtx` (scene + intent + character + environment),
  `Effect` lists, `CharacterSheet`, `CombatState`.
- **Outputs:** `CheckProposal` list, `CheckResult`s, `StateDelta`s,
  `EncounterBudget`.
- **Observable behavior:**
  - Never computes dice math in prose — all numbers come from the
    deterministic engine.
  - Seeded RNG: same seed + same inputs = same result.
  - Produces an auditable roll log entry for every resolution.
- **Acceptance criteria:**
  - Unit tests pass on the canonical PF2e examples (Strike, skill check,
    saving throw, initiative, opposed check) with correct degree-of-success
    math.
  - Deterministic replay of any session reproduces all rolls exactly.

### 3.5 ArchivistAgent

- **Responsibility:** Memory read/write, entity resolution, canon guarding,
  summary tiers. Maintains the campaign vault and keeps the player-facing
  projection synchronized.
- **Inputs:** Full turn transcript on write; scene context + player input on
  read.
- **Outputs:** `MemoryPacket` (on read); vault page upserts, SQLite
  transcripts, LanceDB embeddings, summary updates, `CanonConflict` events,
  player vault sync (on write).
- **Storage architecture:** Two-vault model defined in `docs/specs/VAULT_SCHEMA.md`.
  - **Master vault** (`~/.ttrpg/vault/`) — full canon including GM-only
    secrets, open callbacks, and unresolved plot threads. Never exposed
    directly to the player.
  - **Player vault** (`<campaign_dir>/`) — filtered projection of the master.
    Contains only player-discovered content with GM-only fields stripped.
    Safe to open in Obsidian at any time.
  - A sync step runs after every turn to update the player vault.
  - On campaign end, the player may unlock the full master vault as a
    post-campaign "director's cut" artifact.
- **Observable behavior:**
  - Every named entity resolves to exactly one vault page (no duplicates).
    Resolved via slug matching, frontmatter `aliases`, and LanceDB vector
    similarity in that order.
  - Canon conflicts surface in the next turn's `SceneBrief` rather than
    silently overwriting.
  - Rolling summaries reflect only canonical facts (not player-hypothetical
    musings).
  - Player vault never reveals GM-only content (`visibility: gm_only` pages,
    `secrets` frontmatter fields, `<!-- gm: ... -->` inline blocks).
- **Acceptance criteria:**
  - 10-session recall test: NPC introduced in session 1 is correctly named
    and characterized when reintroduced in session 10.
  - Entity-resolution precision ≥ 0.95 on the fixture suite.
  - `MemoryPacket` never exceeds its configured token cap.
  - Player vault opened in Obsidian after session 5 of the seed campaign
    shows zero GM-only spoiler content.
  - Player vault is valid Obsidian markdown: all `[[wikilinks]]` resolve,
    all YAML frontmatter parses without error.

### 3.6 Supporting services (not agents, but player-affecting)

- **IntentResolver:** turns "I sneak past the guard" into
  `[Skill(Stealth) vs. Perception DC]`. Deterministic rules first, LLM
  fallback.
- **SafetyGuard:** two-phase. Pre-gate blocks redlined scene intents.
  Post-gate scans generated prose; on violation, requests a rewrite up to
  two times then degrades to a terse fallback.
- **CostGovernor:** enforces per-session budget; warns at 70% and 90%; hard
  stops at 100% with a narrative "pause for next session."
  See `docs/specs/LLM_PROVIDER_SPEC.md` for token/cost accounting behavior.
- **DiceService:** seeded, reproducible, auditable; every roll logged with
  seed + inputs + result.

### 3.7 Deferred agents (stubs in MVP)

- **Artist** — `ImageProvider` interface only; MVP returns placeholders.
- **Cartographer** — Oracle emits textual spatial notes only.
- **Puppeteer** — Oracle generates NPCs inline.

## 4. Turn flow (observable)

Default (mechanics-first):

1. Player types input.
2. Short pause (~0.5–1 s) while mechanics resolve off-screen.
3. If `dice_ux=reveal` and a check fires: dice overlay shows DC, mods,
   animated d20, result.
4. Orator narration streams into the TUI with outcomes woven in.
5. Status panel updates (HP, conditions, clock).
6. Prompt returns for next input.

**Late-roll exception:** on rare turns the Orator pauses mid-stream, a dice
overlay resolves the late check, then prose resumes.

**Acceptance criteria:**
- Every turn ends with a readable, re-scrollable transcript entry.
- No dropped turns on network blip: state is checkpointed before narration
  streams.

## 5. Rules (PF2e scope for MVP)

### 5.1 Character creation flow

Three modes (from `PlayerProfile.character_mode`):

- **Guided:** step-by-step wizard (ancestry → background → class → ability
  boosts → skills → equipment). LLM explains each choice.
- **Player-led:** prose description → LLM proposes a sheet → player edits →
  engine validates legality.
- **Pre-generated:** Oracle picks a level-1 archetype fitting the
  campaign.

**Acceptance criteria:** Output `CharacterSheet` passes engine schema
validation before first scene.

**Implementation contract:** The first buildable subset of Pathfinder 2e data
and rules is defined in `docs/specs/PF2E_MVP_SUBSET.md`. If this document and
that subset spec differ, the subset spec controls implementation scope for
the first playable vertical slice.

### 5.2 Core math

DCs by level, degrees of success (crit success / success / failure /
crit failure), proficiency + level + ability mods. Engine tables are the
source of truth.

### 5.3 Actions in MVP

Strike, Stride, Step, Raise a Shield, Seek, Demoralize, Recall Knowledge,
Trip, Grapple, Cast a Spell (curated spell list).

### 5.4 Combat

- 3-action economy + reaction.
- Initiative rolled at combat start (Perception default); turn order
  preserved through checkpoints.
- Theater-of-mind positions: `close | near | far | behind_cover`.
- Conditions tracked: frightened, off-guard, prone, dying/wounded, drained.

### 5.5 Encounter design

Oracle calls `encounter_budget(party_level, difficulty)`; selects from
the ORC bestiary within budget; tags each creature with role (brute,
skirmisher, caster, face).

### 5.6 In-game clock

`minutes | hours | days` tracked. Effect durations, rest, spell slot
recovery, and travel all key off the clock. `/clock` shows current time.

### 5.7 Death and failure

PF2e dying/wounded/dead modeled precisely. `HouseRules.death_policy` selects
narrative response:

- `hardcore`: epilogue, campaign ends.
- `heroic_recovery`: PC revives with narrative cost.
- `retire_and_continue`: new PC takes over.

TPK always triggers narrative handoff, never silent game-over.

## 6. Memory behavior (player-observable)

- The game remembers NPC names, dispositions, promises made, items taken,
  places visited, and unresolved plot threads across sessions indefinitely.
- `/recap` produces a rolling summary of the last session (and on request,
  the current arc).
- `/retcon` removes the last turn from canon with confirmation.
- Canon conflicts (e.g., player says "the innkeeper is a dwarf" but canon
  says "half-elf") are surfaced to the player rather than silently
  resolved.

## 7. Onboarding flow (with examples)

### 7.1 Phases

1. **Welcome + premise selection** ("What kind of adventure draws you
   in?").
2. **Tone + touchstones** ("Name 3 books/games/films the story should feel
   like.").
3. **Pillars + pacing** ("Out of 10 points, how do you split combat /
   exploration / social / puzzle?").
4. **Combat style + dice UX** ("Do you want to see the dice, or have
   outcomes narrated?").
5. **Content lines and veils** ("Are there topics you want off-limits?
   Fade-to-black?").
6. **Campaign length + death policy** ("One-shot, arc, open-ended?
   Hardcore, heroic, retire?").
7. **Budget** ("Per-session token/USD cap; what should happen at the
   cap?").
8. **Character creation mode** ("Guided, describe-in-prose, or
   pre-generated?").
9. **Review + confirm.**

### 7.2 Sample Q&A turn

> **System:** You listed Disco Elysium as a touchstone. Do you want
> internal-monologue-style narration where your character's thoughts,
> instincts, and skills speak up?
>
> **Player:** Sometimes, not constantly.
>
> **System:** Got it — I'll surface inner voices at moments of high tension
> or impactful choice, not during routine action.

## 8. Session UX (TUI)

### 8.1 Layout

- Left (wide): streaming narration.
- Right (narrow): status panel — HP, conditions, active quest, current
  location, in-game clock, last 3 rolls.
- Top: persistent safety bar with `/pause` and `/line`.
- Bottom: input line with `/commands`.

### 8.2 Slash commands

`/save`, `/recap`, `/sheet`, `/inventory`, `/map`, `/clock`, `/budget`,
`/pause`, `/line`, `/retcon`, `/settings`, `/help`.

### 8.3 Dice overlay

- `auto`: flash result for 500 ms, continue.
- `reveal`: modal shows DC + mods; player presses to roll; animated d20;
  result held until dismissed.
- `hidden`: no modal; Orator narrates outcomes.

## 9. Safety and content controls

- Onboarding produces `ContentPolicy` with hard limits (red) and soft
  limits (yellow / fade-to-black).
- `/pause` freezes the turn and opens a dialog (continue, retcon, adjust
  lines).
- `/line` invokes a hard limit mid-scene; Orator fades to black; Oracle
  reroutes.
- All safety events logged to the session log.

**Acceptance criteria:** a session configured with `line=graphic_violence`
produces no graphic-violence prose across a 100-turn regression; `/line`
invoked mid-scene visibly changes the next two turns' content.

## 10. Save and resume

- Checkpoint after every turn.
- Quit any time; `ttrpg play` resumes at the last checkpoint.
- Checkpoints versioned with app semver; older checkpoints migrated or
  flagged.

**Implementation contract:** Turn-close ordering, crash behavior, rebuildable
indices, and checkpoint semantics are defined in
`docs/specs/PERSISTENCE_SPEC.md`.

## 11. Acceptance criteria (MVP DoD)

- Install → `ttrpg init` → add OpenRouter key → onboarding → character
  creation → start campaign, all in one session.
- Play at least one combat encounter and one skill challenge end-to-end.
- Quit and resume next day; NPCs, quests, and events from the prior
  session are correctly recalled.
- A callback seeded in session 1 is paid off in a later session.
- `/pause` and `/line` visibly change subsequent narration.
- All rolls auditable; all extractions traceable.
- CostGovernor enforces per-session budget.
- Eval smoke suite green on release branch.
- Fully local; no server required.

## 12. Minimal example content

### 12.1 Example `SceneBrief`

```json
{
  "scene_id": "s_014",
  "intent": "Introduce the missing-merchant hook in the tavern.",
  "location": "Bent Copper Tavern, Rivermouth",
  "present_entities": ["npc_marcus_innkeeper", "npc_worried_wife_sera"],
  "beats": [
    "Sera approaches the PC with a desperate plea.",
    "She describes her husband's disappearance last night.",
    "She offers a crude map and a modest reward."
  ],
  "success_outs": ["PC accepts the job", "PC gathers more information first"],
  "failure_outs": ["PC declines; Sera leaves; hook may return via a second NPC"],
  "pacing_target": {"pillar": "social", "tension": "rising", "length": "short"},
  "callbacks_seeded": ["cb_missing_merchant_witness"]
}
```

### 12.2 Example NPC record

```json
{
  "id": "npc_marcus_innkeeper",
  "name": "Marcus",
  "species": "Human",
  "role": "Innkeeper of the Bent Copper",
  "disposition": "friendly",
  "voice": "weary, dry humor, uses sailing metaphors",
  "secrets": ["Owes a debt to the riverboat guild"],
  "stats_ref": "commoner_cr0_variant"
}
```

### 12.3 Example encounter

```json
{
  "id": "enc_river_ambush",
  "difficulty": "moderate",
  "party_level": 1,
  "budget_xp": 80,
  "creatures": [
    {"ref": "goblin_warrior", "count": 2, "role": "skirmisher"},
    {"ref": "goblin_commando", "count": 1, "role": "brute"}
  ],
  "terrain_tags": ["rocky", "riverbank", "low_cover"],
  "trigger": "PC crosses the shallow ford."
}
```

### 12.4 Example onboarding output excerpt

```json
{
  "profile": {
    "genre": ["low_fantasy_noir"],
    "tone": ["moody", "morally_grey"],
    "touchstones": ["Disco Elysium", "The Witcher"],
    "pillar_weights": {"social": 0.4, "exploration": 0.3, "combat": 0.2, "puzzle": 0.1},
    "combat_style": "theater_of_mind",
    "dice_ux": "reveal",
    "death_policy": "heroic_recovery"
  }
}
```
