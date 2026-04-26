# Feature Landscape: SagaSmith

**Domain:** Local-first AI-run solo tabletop RPG assistant / AI GM in a Textual TUI  
**Project:** SagaSmith  
**Researched:** 2026-04-26  
**Research focus:** Features required for v1/MVP, differentiators, deferred wishlist boundaries, and anti-features based on existing SagaSmith specs plus current AI RPG / solo RPG assistant ecosystem.

## Summary Recommendation

SagaSmith's MVP should not try to out-feature cloud AI RPG platforms on visuals, multiplayer, tactical battlemaps, world-sharing, or breadth of rule systems. Those are expensive categories where established products already compete. SagaSmith should instead ship a tight local-first solo PF2e vertical slice whose trust guarantees are unusually strong: deterministic/auditable mechanics, persistent multi-session memory, spoiler-safe Obsidian vaults, BYOK model/cost controls, and safety controls that work during play.

For v1, the product lives or dies on whether the player can install it, bring an LLM key, complete onboarding, play a meaningful scene, resolve mechanics correctly, quit, resume, and see that the world remembered them. If any of those fail, the product feels like a tech demo rather than a solo RPG. The strongest differentiator is not "AI can narrate"; that is now table stakes. The differentiator is "AI improvises while deterministic local services preserve rules, memory, safety, budget, and persistence."

## Ecosystem Signals

| Signal | Product / Source | Feature implication for SagaSmith | Confidence |
|--------|------------------|-----------------------------------|------------|
| AI RPG platforms emphasize open-ended natural-language play, unscripted NPC interaction, progression, deterministic systems, persistence, and continuity. | Latitude Voyage launch coverage, TechCrunch 2026-04-21 | Free-form action input and continuity are table stakes; deterministic gameplay systems are expected for anything beyond pure fiction. | MEDIUM - TechCrunch report, not product docs |
| AI TTRPG platforms emphasize AI GM, rules handling, stat tracking, notes, worldbuilding, solo/multiplayer, maps/tokens, and long-term context. | Friends & Fables official about page and public feature descriptions | SagaSmith must at least track sheet/state/rules and notes; it can defer maps/multiplayer because its positioning is local-first solo. | HIGH for official page, MEDIUM for third-party feature summaries |
| AI Dungeon exposes memory systems, story cards, scenarios, scripting, publishing, and configurable safety settings. | AI Dungeon Guidebook / official help | Memory and safety customization are expected in AI story products; public publishing/scripting are not MVP-aligned. | HIGH |
| AI Dungeon replaced simplistic safe mode with more granular safety levels because users wanted better control over uncomfortable outputs. | AI Dungeon safety docs | SagaSmith's lines/veils, `/pause`, `/line`, and visible safety event logging are table stakes for trust, not extras. | HIGH |
| Solo RPG oracle apps emphasize fast oracle consultation, scene tracking, journals, character/thread lists, automatic save, export/import, dice roller, and local storage. | Mythic GME 2e official app page; One Page Solo Engine listings | Recaps, journals/transcripts, save/resume, dice, and thread/callback tracking are table stakes for solo play. | HIGH for Mythic official page, MEDIUM for app listings |
| AI RPG content tools emphasize NPCs, quests, encounters, locations, monsters, items, generators, public libraries, and multiple systems. | LitRPG Adventures official site | Content generation is common, but SagaSmith should generate only what's needed for play and defer creator-library/platform features. | HIGH |

## Table Stakes

Features users reasonably expect from a playable local-first AI solo RPG. Missing these in v1 risks users leaving or concluding the game is unreliable.

| Feature | Why Expected | Complexity | Dependencies | MVP Scope / Notes |
|---------|--------------|------------|--------------|-------------------|
| Local install and first-run setup | Local-first is the core promise; users should not need a hosted server. | Medium | Packaging, app dirs, config, Textual CLI/TUI shell | Must include. `ttrpg init` or equivalent should create campaign directory, SQLite DB, and player vault location. |
| BYOK LLM provider setup | SagaSmith depends on user-provided credentials; failure here blocks play. | Medium | `LLMClient`, OpenRouter client, keyring/env var secret references, redacted logging | Must include OpenRouter first. Direct providers can wait if the interface is stable. Never persist plaintext keys. |
| Guided onboarding interview | AI RPG players expect personalization; solo RPG players need tone, premise, safety, and playstyle set before play. | Medium | OnboardingAgent, JSON Schema/Pydantic validation, SQLite persistence, editable review screen | Must include profile, content policy, house rules, budget, dice UX, campaign length, and character mode. Keep under 15 minutes. |
| Campaign start / hook selection | AI GM products must create a playable premise quickly; blank screens kill momentum. | Medium | Onboarding output, Oracle world seed, Orator narration, vault write | Must include 3-5 hooks or a curated first slice hook. For first vertical slice, prefer one curated sample campaign path plus limited choice. |
| Free-form natural-language player input | "Go anywhere, do anything" requires text input beyond menu choices. | High | TUI input, intent resolution, safety pre-gate, rules proposal, Oracle routing | Must include for non-combat scene actions. Limit mechanics handled, not language accepted. |
| Streaming narration | AI story tools feel slow and dead without progressive output. | Medium | LLM streaming, OratorAgent, transcript buffer, retry/fallback handling | Must include Orator streaming with first-token target around spec's p50 <2s on healthy connection. |
| One authoritative narrative voice | Without a single voice, multi-agent output feels incoherent and exposes implementation seams. | Medium | Oracle/Orator separation, prompt contracts, routing | Must include. Oracle plans; Orator narrates. No direct Oracle narration to player. |
| Deterministic dice and roll logs | TTRPG players expect dice fairness and reproducibility; AI cannot be trusted to invent rolls. | Medium | DiceService seeded RNG, roll schema, roll log table, replay tests | Must include before AI gameplay. Every check logs seed, inputs, d20, total, DC, degree. |
| Auditable PF2e core resolution | Rules correctness is central to "tabletop" positioning and differentiates from pure story chat. | High | PF2e data subset, RulesLawyerAgent/service, DiceService, tests | Must include first-slice subset: level 1 pregenerated martial PC, skill check, Perception initiative, Strike vs AC, HP damage, simple combat. |
| Character sheet visibility | Players need to inspect the PC and trust that mechanics use the sheet. | Medium | CharacterSheet schema, TUI sheet panel/command, rules engine | Must include `/sheet` for pregen. Guided/player-led creation can be deferred beyond first slice but belongs in full MVP. |
| Status panel | RPG state must be visible: HP, conditions, active quest, location, clock, recent rolls. | Medium | Textual layout, state model, turn updates | Must include core fields. Conditions can show empty/none in first slice. |
| Dice UX modes | Existing specs promise auto/reveal/hidden; users differ on how much mechanics they want exposed. | Medium | Dice overlay, HouseRules.dice_ux, Orator integration | Must include at least `reveal` and a simple `hidden`/`auto` behavior. Rich dice visuals are deferred. |
| Save, quit, and resume | Persistent campaigns are a core value. Losing state is unacceptable. | High | SQLite transaction, LangGraph checkpoint, vault write ordering, app command dispatch | Must include checkpoint after every completed turn and resume at next prompt. |
| Crash/network failure recovery | LLM apps fail; a local-first RPG must not corrupt canon on stream failure. | High | Pre-narration checkpoint, retry policy, transcript failure events, turn status | Must include basic recovery path: rerun narration or discard incomplete turn. |
| Campaign transcript / scrollback | Solo RPG apps and AI story tools both rely on a readable journal/history. | Medium | Transcript table, TUI scrollback, persistence | Must include re-scrollable turn entries. Export can be deferred if vault/session pages exist. |
| Recap command | Solo campaigns resume across days; players need a quick memory refresh. | Medium | Archivist summaries, transcript storage, Orator rendering | Must include `/recap` for last session/current arc, even if first implementation uses deterministic transcript summary plus LLM polish. |
| Persistent campaign memory | AI RPGs compete on continuity; without memory SagaSmith is just a chatbot. | High | ArchivistAgent, vault schema, SQLite/FTS/LanceDB interfaces, MemoryPacket caps | Must include NPCs, quests, places, promises, items, and unresolved threads across sessions. First slice can use small fixture-backed memory. |
| Entity resolution | Duplicate NPC/location pages erode trust and pollute memory. | High | Slug/alias matching, vector similarity later, vault schema | Must include slug + alias matching. Vector similarity can be stubbed until LanceDB integration lands. |
| Spoiler-safe player-facing notes | Players should be able to inspect campaign notes without seeing hidden GM planning. | High | Two-vault projection, visibility states, GM field stripping, atomic sync | Must include because it is central to SagaSmith's unique memory promise. |
| Obsidian-compatible player vault | Local-first users value durable, readable artifacts; solo RPG users often journal. | Medium | Markdown vault schema, wikilinks, YAML validation, sync command | Must include known NPCs, locations, quests, log/index pages. This is also a differentiator. |
| Safety onboarding and runtime controls | AI story products can generate unwanted content; user control is now expected. | High | ContentPolicy, SafetyGuard pre/post gates, commands, reroute logic | Must include hard limits, soft limits/fade-to-black, `/pause`, `/line`, visible safety events. |
| Budget/cost visibility and hard stop | BYOK users need confidence the app will not unexpectedly spend money. | Medium | Token usage, pricing table, CostGovernor, TUI budget command | Must include `/budget`, 70%/90% warnings, hard stop before next paid call. |
| Required slash commands | Terminal RPGs need discoverable control commands. | Medium | Command parser, TUI help, service hooks | Must include `/save`, `/recap`, `/sheet`, `/inventory`, `/clock`, `/budget`, `/pause`, `/line`, `/retcon`, `/settings`, `/help`. `/map` can be text-only. |
| Retcon last turn | Solo play often involves interpretation mistakes; specs promise reversible canon. | High | Inverse deltas, turn status, vault rebuild/sync | Must include at least last-turn confirmation and rollback for simple state/vault updates. More complex manual correction can be deferred. |
| Inventory basics | PF2e and adventure play require knowing carried items/rewards. | Medium | CharacterSheet, vault item pages, `/inventory` | Must include minimal inventory view/update. Full item database can be deferred. |
| In-game clock | Exploration, travel, duration, session recaps, and vault pages need temporal grounding. | Medium | SessionState clock, `/clock`, Orator/Oracle constraints | Must include simple minutes/hours/days tracking. Detailed downtime can wait. |
| Skill challenge + simple combat vertical slice | A solo AI TTRPG must prove both noncombat and combat loops. | High | Rules engine, Oracle encounter request, Orator, TUI state updates | Must include one skill challenge and one theater-of-mind combat, two enemies max, no spellcasting first slice. |
| Eval/smoke regression | AI RPG quality regresses invisibly without scenario tests. | Medium | Fixture campaign, deterministic replay, transcript assertions | Must include smoke flow, rules examples, memory recall, safety redline, cost enforcement. |

## Differentiators

Features that are not universally expected in every AI RPG tool but can make SagaSmith meaningfully different. These should be protected in roadmap prioritization because they support the core value proposition.

| Feature | Value Proposition | Complexity | Dependencies | MVP Treatment |
|---------|-------------------|------------|--------------|---------------|
| Local-first, durable campaign artifact | Player owns the campaign data as files/SQLite rather than renting access to a cloud story. | High | App data layout, vault schema, SQLite, rebuild/sync tools | Must include. This is core positioning, not polish. |
| Two-vault spoiler-safe memory | Lets the app maintain GM secrets while giving the player an Obsidian-safe fan wiki. Most AI RPGs emphasize memory, but not spoiler-safe local vault ownership. | High | Master vault, player projection, visibility states, stripping, tests | Must include a minimal but real version in MVP. |
| Deterministic-service / AI-agent split | Builds trust: AI creates and narrates, code resolves mechanics, persistence, cost, and safety. | High | LangGraph state, typed schemas, tool boundaries, evals | Must include. This is the architecture behind SagaSmith's reliability claim. |
| Auditable PF2e math under improvised narrative | Satisfies crunchy TTRPG players who bounce off pure AI fiction due to hallucinated rules. | High | PF2e subset engine, local rules data, roll logs | Must include first-slice subset. Expand breadth later. |
| Player-configurable dice opacity | Supports both narrative-first and rules-visible players without forking the core loop. | Medium | HouseRules, dice overlay, Orator constraints | Must include basic modes. Rich animations are v2. |
| Safety as an in-fiction reroute system | `/line` should not merely error; it should fade/reroute and continue the game safely. | High | ContentPolicy, SafetyGuard, Oracle reroute, Orator rewrite | Must include minimal implementation because it strongly supports trust. |
| CostGovernor as first-class gameplay control | BYOK AI games often hide cost risk; SagaSmith can earn trust by making cost visible and enforceable. | Medium | Provider usage/cost logging, budget UI, fallback messaging | Must include warnings and hard stop. |
| Canon conflict surfacing | Instead of silently overwriting contradictory facts, the game exposes conflicts. This makes memory feel trustworthy. | High | Archivist entity/canon checks, Oracle integration, player-facing messaging | Should include in full MVP. First slice can implement simple NPC/location contradiction warnings. |
| Rebuildable derived memory layers | Local repair commands make long campaigns survivable and debuggable. | Medium | Vault as source of truth, FTS5/LanceDB/NetworkX adapters | Include `vault sync`/basic validation early; defer full LanceDB/NetworkX if needed. |
| Callback ledger / seed-to-payoff tracking | Makes AI campaign arcs feel intentional rather than endlessly improvisational. | High | Oracle callback records, vault callbacks, Archivist recall | Include at least one seed-to-payoff in MVP smoke campaign. |
| Typed structured outputs for agents | Reduces hallucinated state and enables validation/retry. | Medium | JSON schemas/Pydantic, provider response_format support | Must include for Oracle/Archivist/Onboarding outputs. |
| Minimal TUI with always-visible trust surfaces | A terminal UI can differentiate by being fast, readable, and explicit about state, dice, safety, and budget. | Medium | Textual layout, status panel, slash commands | Must include. Avoid GUI envy; make the TUI excellent for text play. |

## V1 Must Include

This is the recommended MVP requirement cut. It balances user expectations, SagaSmith's differentiators, and the explicit first-slice boundaries in the specs.

### 1. Installation, Setup, and Campaign Creation

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| `ttrpg init` / first-run flow creates local campaign directory, SQLite DB, and player vault. | Medium | Packaging, path management, vault schema | User can start without a hosted server. |
| Configure OpenRouter credential by keyring/env reference. | Medium | LLM provider abstraction, redacted logs | No plaintext key in campaign files, vaults, transcripts, checkpoints, or debug logs. |
| Choose or create campaign name/location. | Low | App config, file paths | Campaign appears in local user-chosen folder. |
| Provider/model settings screen. | Medium | LLM config schema, TUI settings | Default, narration, and cheap model stored by reference/config, not secrets. |

### 2. Onboarding and Safety Contract

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| Structured onboarding interview. | Medium | OnboardingAgent, schemas | Produces `PlayerProfile`, `ContentPolicy`, `HouseRules`. |
| Editable review screen before commit. | Medium | TUI forms, validation | Player can correct preferences before gameplay. |
| Lines/veils and runtime safety commands. | High | SafetyGuard, command parser, Oracle/Orator contracts | `/pause` freezes; `/line` reroutes/fades; events logged. |
| Budget setup. | Medium | CostGovernor, provider pricing | Budget warning and hard-stop thresholds configured before first play. |

### 3. First Playable Story Loop

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| Generate or select a first hook. | Medium | Oracle, onboarding profile | Player starts with clear premise, not a blank prompt. |
| Free-form player input. | High | TUI input, intent resolver, safety gate | Natural-language action accepted each turn. |
| Oracle produces structured scene plan. | High | LangGraph routing, schemas, profile/memory | `SceneBrief` validates and contains intent/beats/entities/outcomes. |
| Orator streams narration. | Medium | LLM streaming, transcript buffer | First complete beat streams and respects tone/safety/dice UX. |
| Turn transcript persists. | Medium | SQLite transcript, TUI scrollback | Every completed turn is readable after resume. |

### 4. Deterministic PF2e First Slice

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| One level-1 pregenerated martial PC. | Medium | CharacterSheet schema, local data | `/sheet` displays valid sheet. |
| Skill check vs fixed DC. | Medium | DiceService, degree-of-success engine | Logs d20, modifier, DC, degree. |
| Perception initiative. | Medium | DiceService, combat state | Initiative order persists through checkpoint. |
| Strike vs AC and HP damage. | High | Creature data, combat state, action economy | Simple combat completes end-to-end. |
| Theater-of-mind positions. | Medium | Combat state, Orator constraints | Position tags: close/near/far/behind_cover. |
| Roll replay tests. | Medium | Seeded RNG, fixture tests | Same seed + inputs reproduce exact rolls. |

### 5. Memory, Vault, and Resume

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| SQLite campaign DB for profiles, turns, transcripts, rolls, checkpoints, cost logs. | High | Persistence layer, migrations | Completed turns survive restart. |
| Master vault writes for known campaign entities. | High | Vault schema, atomic file replacement | NPC/location/quest pages validate YAML. |
| Player vault projection. | High | Visibility stripping, sync order | Player vault contains no GM-only fields/comments. |
| `index.md` and `log.md` generation. | Medium | Vault sync | Obsidian-friendly overview updates after turns. |
| `/recap` command. | Medium | Transcript summaries, Archivist | Last session/current arc summary available. |
| `/retcon` last completed turn. | High | State deltas, vault rebuild/sync | Confirmed retcon removes last turn from canon for simple cases. |
| Quit/resume at last safe prompt. | High | Checkpoints, turn lifecycle | Resume next day recalls NPCs/events from prior session. |

### 6. Trust and Control UI

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| Textual layout: narration, status, input, safety bar. | Medium | Textual app shell | Player always sees action context and safety affordance. |
| Status panel: HP, conditions, active quest, location, clock, last rolls. | Medium | State model, TUI refresh | Updates after mechanics resolve. |
| Dice overlay for reveal mode. | Medium | DiceService, TUI modal | Shows DC/mod/result and resumes narration. |
| Slash command help. | Low | Command registry | `/help` lists available commands and descriptions. |
| `/budget`, `/clock`, `/inventory`, `/settings`. | Medium | Services and TUI views | Player can inspect/control game state. |

### 7. Quality Gate / Evals

| Requirement | Complexity | Dependencies | Acceptance Target |
|-------------|------------|--------------|-------------------|
| Rules unit tests. | Medium | PF2e engine | Degree boundaries, n1/n20, Strike, skill, initiative, HP. |
| Smoke campaign fixture. | High | Full loop | Install/init/onboard/play skill/combat/quit/resume passes. |
| Memory recall regression. | High | Archivist/vault | Session 1 NPC correctly recalled later. |
| Safety redline regression. | Medium | SafetyGuard | Configured hard line does not appear in generated prose. |
| Cost enforcement regression. | Medium | CostGovernor | 70/90 warnings and hard stop occur before over-budget call. |

## V2 / Deferred

These features are valuable but should not be required for v1. Many are explicitly deferred in `docs/WISHLIST.md` or exceed the first vertical slice.

| Feature | Why Defer | Complexity | Dependencies / Future Trigger |
|---------|-----------|------------|-------------------------------|
| Guided character creation wizard | First slice can prove gameplay with a pregen; PF2e character creation is data-heavy. | High | Expanded PF2e data, validation UI, LLM explanation | Promote after rules engine is stable. |
| Player-led prose-to-sheet generation | High hallucination risk and legality validation burden. | High | Character builder, rules validation, edit UI | Promote after guided creation works. |
| Spellcasting | PF2e spells introduce saves, ranges, areas, traits, durations, resources, and many exceptions. | High | Saving throws, spell data, action economy, conditions | Defer until martial combat foundation is stable. |
| Full PF2e levels 1-3 | MVP target but not first slice; data and feat/action breadth is significant. | Medium-High | Rules data expansion, condition system, encounter budgets | Phase after first slice tests pass. |
| PF2e levels 4+ | Data volume and progression complexity; not needed for initial validation. | Medium | Full feat/class/equipment tables | Post-MVP. |
| Multiple rules systems | Each ruleset requires data, engine behavior, tests, and UX. | Very High | RulesEngine Protocol maturity, community demand | Post-MVP. |
| Custom/homebrew rule-system builder | Effectively a rules DSL and interpreter. | Very High | Mature rules abstraction, content/modding ecosystem | Long-term. |
| Tactical grid / battlemaps | Competes with VTTs; high UI and rules complexity. | High | Cartographer, map renderer, spatial engine, tactical UI | Post-MVP. Keep theater-of-mind tags. |
| CartographerAgent | Spatial consistency beyond text notes is not required for first playable loop. | Medium-High | Location graph, map generation, Orator grounding | Post-MVP. |
| ArtistAgent / image generation | Expensive, latency-prone, style consistency problem; not core to text TUI validation. | High | ImageProvider, asset storage, safety checks, style guides | Keep placeholder only. |
| Rich dice animation/themes | Nice feel, not required for trust. | Low-Medium | TUI animation/assets | Improve after functional dice overlay. |
| GUI / web / Tauri frontend | Would dilute scope and duplicate interface work. | Medium-High | Stable backend API | Post-MVP after TUI validates loop. |
| Mobile companion app | Requires API/sync strategy and frontend. | Medium | Stable local data/export or server bridge | Long-term. |
| Voice input/output | Accessibility and immersion value, but not central to text-first MVP. | Low-High | STT/TTS providers, cost, latency, safety | Post-MVP. |
| Multiplayer / party play | State sync, conflicting intents, party mechanics, cost allocation. | Very High | Server/network model, multi-PC rules, shared memory | Explicitly out of scope. |
| Party companions / multi-PC | Adds narrative agency, companion state, party balance. | Medium-High | Multi-character combat, NPC behavior, relationship system | Post-MVP. |
| PuppeteerAgent | Inline NPCs are enough for small MVP world. | High | NPC schedules/goals/memory, faction systems | Add when NPC count/world complexity demands it. |
| VillainAgent | Persistent antagonists with schemes are compelling but need their own planning loop/evals. | High | Oracle authority split, villain memory, encounter composer | Post-MVP. |
| Community content / campaign sharing platform | Requires accounts, moderation, hosting, discovery. | High | Hosted service and content pipeline | Contradicts local-first MVP focus. |
| Public scenario publishing / scripting | Strong in AI Dungeon-like ecosystems but undermines v1 focus. | High | Sandbox, security, moderation, authoring tools | Defer until core game is validated. |
| Rich content generator suite | LitRPG-style generators are useful but not a playable game loop. | Medium | Standalone tool UI, content library | Generate only play-needed content in MVP. |
| Dedicated graph database | NetworkX/FTS/LanceDB derived layers are sufficient for MVP scale. | Low-Medium | Query scale pain, very long campaigns | Consider Kuzu only if NetworkX becomes insufficient. |
| Director mode | Useful for advanced users/human GMs but changes product mode. | Medium | Oracle override UI, command permissions | Post-MVP. |
| Master vault unlock / director's cut | Valuable artifact at campaign end; not required before active campaign loop works. | Medium | Mature vault projection, campaign end flow | Could be V1.1 if vault is already robust. |

## Anti-Features

Features or design choices SagaSmith should deliberately avoid for v1 because they conflict with the product promise, create disproportionate complexity, or imitate competitors in the wrong direction.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| AI-invented mechanics | Destroys trust with PF2e players; makes replay and audit impossible. | Deterministic engine owns all modifiers, DCs, damage, HP, conditions, action economy, and encounter budgets. |
| Full PF2e breadth before a playable slice | Data/rules completeness can consume months without proving fun. | Implement level-1 martial pregen, one skill challenge, one simple combat first. |
| Tactical battlemaps in v1 | High-complexity VTT problem; distracts from memory/narrative/rules loop. | Use theater-of-mind tags and clear prose/status panel. |
| Multiplayer in v1 | Requires networking, sync, multi-user permissions, cost rules, and party mechanics. | Optimize solo player + solo PC experience. |
| GUI/web/mobile frontend in v1 | Multiplies surface area before core loop is validated. | Make the Textual TUI readable, fast, keyboard-first, and transparent. |
| Hosted cloud account dependency | Contradicts local-first ownership and adds operations burden. | BYOK provider calls only; all campaign state local. |
| Storing API keys in campaign files or logs | Severe privacy/security failure. | Store keyring/env references only; redact request/response logs. |
| Player edits to vault as canonical state | Creates sync conflicts and ambiguity over source of truth. | Treat player vault as read-only artifact; canon changes happen via commands like `/retcon` and later `/note`. |
| Exposing master vault during active campaign | Spoils GM-only planning and breaks the solo-GM illusion. | Keep master vault in app data; project only safe player vault. |
| Black-box memory that cannot be inspected or repaired | Long campaigns need debuggability and user trust. | Use Obsidian-compatible markdown as source of truth plus rebuild/sync commands. |
| Endless generator tools without gameplay integration | Content generators alone are not a game and compete with mature generator products. | Generate only content required by the active scene/campaign; persist it as canon. |
| Public world marketplace / sharing in MVP | Moderation, copyright, safety, and hosting complexity. | Ship local seed/demo vault fixtures only. |
| AI art pipeline in MVP | Cost, latency, consistency, safety, and storage burden; not central to terminal text play. | Keep `ImageProvider` placeholder and optional panel slot. |
| Rich procedural dungeon/hex generation in MVP | Spatial systems imply map consistency and tactical affordances SagaSmith is deferring. | Use textual locations and simple travel/position tags. |
| Dedicated Villain/Puppeteer/Cartographer agents in MVP | Agent proliferation increases coordination and eval complexity before the core loop works. | Keep Oracle responsible for inline NPCs, antagonists, and spatial notes. |
| Mature-content free-for-all | AI story products need safety controls; ignoring this creates user harm and support risk. | Offer explicit content policy, hard/soft limits, `/pause`, `/line`, and logged safety events. |
| Overly restrictive one-size-fits-all safe mode | Users need nuanced control; broad filters can frustrate play and still miss unwanted content. | Use player-defined lines/veils plus runtime reroutes and visible controls. |
| Hidden/uncapped LLM spend | BYOK users will churn if costs surprise them. | Show `/budget`, warnings at 70/90%, and hard-stop before over-budget calls. |
| Relying on LLM context window as memory | Causes drift and context loss; does not satisfy persistent campaign promise. | Store canon in vault/SQLite and assemble bounded MemoryPackets. |
| Canon overwrite on contradiction | Silently changing facts makes the world feel fake. | Detect conflicts and surface them to player/Oracle for resolution. |
| Building for high-level PF2e balance before low-level flow | High-level mechanics are not needed to validate AI GM experience. | Cap early play at level 1 first slice, then levels 1-3 full MVP. |
| Obsidian plugin dependency | Local artifact should be readable without requiring a user's plugin setup. | Use standard markdown, YAML frontmatter, wikilinks; plugins optional only. |

## Dependencies

Feature dependencies that should shape implementation order and requirements decomposition.

```text
Local app scaffold
  -> campaign directory + app data paths
  -> SQLite campaign DB
  -> vault root creation
  -> Textual TUI shell

LLM provider setup
  -> OpenRouter client
  -> structured JSON calls
  -> streaming calls
  -> token/cost usage capture
  -> CostGovernor warnings/hard stop
  -> Oracle/Orator/Onboarding integration

Typed state schemas
  -> onboarding records
  -> character/combat/session state
  -> agent structured outputs
  -> persistence validation
  -> eval fixtures

Onboarding
  -> PlayerProfile
  -> ContentPolicy
  -> HouseRules
  -> budget and dice UX settings
  -> Oracle campaign seed
  -> Orator tone/safety constraints

Safety controls
  -> ContentPolicy from onboarding
  -> pre-generation gate for scene intents
  -> post-generation scan/rewrite/fallback
  -> `/pause` and `/line` commands
  -> safety event log

Rules foundation
  -> DiceService seeded RNG
  -> degree-of-success math
  -> roll log schema
  -> level-1 pregen CharacterSheet
  -> skill checks / initiative / Strike / HP damage
  -> simple combat encounter
  -> deterministic replay tests

Gameplay turn loop
  -> player input
  -> safety pre-gate
  -> intent/mechanics proposal
  -> deterministic rules resolution
  -> pre-narration checkpoint
  -> Orator streaming
  -> transcript/roll/cost/state persistence
  -> vault writes and player projection
  -> prompt return

Memory/vault
  -> master vault schema
  -> atomic writes
  -> player vault projection
  -> GM-only stripping
  -> index/log generation
  -> entity resolution
  -> MemoryPacket assembly
  -> recap and resume

Retcon
  -> completed turn records
  -> StateDelta/inverse delta tracking
  -> vault rebuild from prior canon
  -> derived index rebuild/sync

Full MVP character creation
  -> broader PF2e data
  -> rules legality validation
  -> guided/player-led UI
  -> sheet edit/confirm flow

Spellcasting / levels 1-3 expansion
  -> saving throws
  -> conditions
  -> durations and resources
  -> curated spell list
  -> encounter budget validation
```

## Recommended Phase Cut for Requirements

1. **Foundation / Trust Services**
   - Local app scaffold, SQLite, schemas, OpenRouter, CostGovernor, DiceService, PF2e degree math.
   - Rationale: every player-facing feature depends on trustworthy local state, secrets handling, cost accounting, and deterministic rolls.

2. **Onboarding + TUI Control Surface**
   - Textual layout, onboarding records, safety/budget/dice preferences, slash command registry.
   - Rationale: establishes the player's contract before any AI GM output.

3. **Rules-First Vertical Slice**
   - Pregen sheet, skill check, initiative, Strike, HP, simple combat, roll logs, replay tests.
   - Rationale: prove mechanics before letting narrative agents depend on them.

4. **AI GM Story Loop**
   - Oracle scene plans, Orator streaming, free-form input, transcript persistence, one skill challenge + one combat.
   - Rationale: makes the game playable while staying inside deterministic boundaries.

5. **Memory + Vault Differentiator**
   - Master/player vault, entity pages, recap, player-safe projection, resume recall, callback ledger.
   - Rationale: converts a playable demo into SagaSmith's differentiated local-first campaign product.

6. **Hardening + Full MVP Expansion**
   - Retcon robustness, rebuild/sync, guided character creation, levels 1-3 expansion, selected conditions/actions, eval coverage.
   - Rationale: deepen reliability and rules coverage only after the end-to-end loop works.

## Sources

- SagaSmith project/spec sources read locally: `.planning/PROJECT.md`, `docs/specs/GAME_SPEC.md`, `docs/specs/PF2E_MVP_SUBSET.md`, `docs/specs/PERSISTENCE_SPEC.md`, `docs/specs/LLM_PROVIDER_SPEC.md`, `docs/specs/VAULT_SCHEMA.md`, `docs/WISHLIST.md`.
- Friends & Fables official about page, retrieved 2026-04-26: https://fables.gg/about — HIGH confidence for AI GM, worldbuilding, stat/note tracking, accessibility positioning.
- AI Dungeon Guidebook advanced feature index, retrieved 2026-04-26: https://help.aidungeon.com/advanced — HIGH confidence for memory, story cards, scenarios, scripting, publishing, ratings feature categories.
- AI Dungeon official safety docs, retrieved 2026-04-26: https://help.aidungeon.com/faq/managing-content-safety-in-ai-dungeon — HIGH confidence for player-controlled AI safety levels and rationale.
- TechCrunch coverage of Latitude Voyage launch, published 2026-04-21, retrieved 2026-04-26: https://techcrunch.com/2026/04/21/voyage-is-an-ai-rpg-platform-for-creating-custom-gaming-worlds-with-ai-generated-npc-interactions/ — MEDIUM confidence for Voyage features and market direction.
- Word Mill Games official Mythic GME 2e app page, retrieved 2026-04-26: https://www.wordmillgames.com/mythic-gme-2e-app.html — HIGH confidence for solo oracle app feature expectations: fate checks, scene tracking, adventure journal, lists, dice, local storage/export/import.
- LitRPG Adventures official site, retrieved 2026-04-26: https://www.litrpgadventures.com/ — HIGH confidence for AI RPG content-generation tool categories and supported systems.
- One Page Solo Engine public app/listing search results, retrieved 2026-04-26 — MEDIUM confidence for solo engine features such as oracle questions, story chain, dice, save/load, custom tables, notes, and exports.
