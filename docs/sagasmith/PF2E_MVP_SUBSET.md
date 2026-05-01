# SagaSmith - Pathfinder 2e MVP Subset

**Status:** Draft  
**Audience:** Implementers of RulesLawyerAgent, DiceService, character
creation, combat state, and mechanical evals.  
**Companion specs:** `GAME_SPEC.md`, `STATE_SCHEMA.md`.

## 1. Purpose

The product MVP names Pathfinder 2e levels 1-3 as the rules target. That is
too large for the first code milestone. This document defines the mechanical
subset that must work first and the expansion path to the full MVP.

## 2. Source of Truth

- The deterministic engine is the source of truth for all math.
- LLM agents may propose checks, but may not invent modifiers, DCs, damage,
  degrees of success, HP changes, or conditions.
- Rules data should be stored as local data files with explicit source notes.
- Only ORC-compatible/open content should be bundled.

## 3. Vertical Slice Rules Scope

The first playable vertical slice supports:

- Level 1 only.
- One pregenerated PC.
- One skill challenge.
- One simple combat encounter.
- Theater-of-mind positions only.
- No spellcasting in the first slice.

## 4. Character Data

First pregenerated PC:

- Level 1 martial character.
- One melee Strike.
- One ranged Strike.
- Trained Perception.
- Four trained skills.
- Shield optional, but only if `Raise a Shield` is implemented.

Required sheet fields are defined in `STATE_SCHEMA.md`.

Guided character creation and player-led sheet generation are full MVP work,
not first-slice work.

## 5. Supported Checks

First slice:

- Skill check vs. fixed DC.
- Perception initiative.
- Strike vs. AC.
- Basic saving throw may be stubbed until spell/hazard support lands.

Full MVP expansion:

- Saving throw.
- Opposed check.
- Recall Knowledge.
- Demoralize.
- Trip.
- Grapple.

## 6. Degree of Success

Implement before any content work:

- Natural 20 raises degree by one.
- Natural 1 lowers degree by one.
- Total >= DC + 10 is critical success.
- Total >= DC is success.
- Total <= DC - 10 is critical failure.
- Else failure.

Unit tests must cover each boundary and natural 1/20 adjustment.

## 7. Actions

First slice actions:

- Strike.
- Stride.
- Step.
- Seek.

Full MVP actions:

- Raise a Shield.
- Demoralize.
- Recall Knowledge.
- Trip.
- Grapple.
- Cast a Spell using a curated spell list.

## 8. Combat

First slice combat:

- Two enemies maximum.
- 3-action economy.
- Initiative order.
- HP damage.
- Defeat at 0 HP for NPCs.
- PC dying/wounded may be simplified to "downed" for first slice, but full MVP
  must implement PF2e dying/wounded/dead precisely.

Position tags:

- `close`
- `near`
- `far`
- `behind_cover`

## 9. Conditions

First slice:

- none required beyond HP state.

Full MVP:

- frightened
- off-guard
- prone
- dying
- wounded
- drained

## 10. Encounter Data

First slice needs two creature records:

- One weak melee enemy.
- One weak ranged or skirmisher enemy.

Each creature record must include:

- `id`
- `name`
- `level`
- `ac`
- `max_hp`
- `perception_modifier`
- `attacks`
- `saves`
- `xp_value`

Full MVP adds encounter XP budget validation for levels 1-3.

## 11. Dice and Replay

All mechanical checks use DiceService:

- Seeded RNG.
- Roll log entry for every die roll.
- Same seed plus same ordered check inputs produces the same result.

Replay tests must assert exact roll reproduction.

## 12. Acceptance Tests

Before Oracle or Orator integration, RulesLawyer must pass:

- Degree-of-success boundaries.
- Seeded d20 replay.
- Skill check success/failure.
- Strike hit/miss/critical hit.
- Initiative ordering.
- HP damage application.
- Roll log completeness.

These tests are blocking for the first playable vertical slice.
