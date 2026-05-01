# RulesLawyerAgent Skills Catalog

**Status:** Draft  
**Audience:** Implementers of deterministic PF2e mechanics, check proposal
handling, combat state, and replay tests.  
**Companion specs:** `GAME_SPEC.md` §3.4 and §5, `STATE_SCHEMA.md`,
`PF2E_MVP_SUBSET.md`.

## 1. Scope Context

RulesLawyer translates player intent and scene context into mechanical checks,
runs deterministic PF2e resolution, emits auditable roll results, and applies
state deltas. It does not narrate outcomes and does not invent rules data.

## 2. Skills

### 2.1 `degree-of-success`

**Purpose:** Compute PF2e degree of success from roll total, DC, and natural
d20 value.

**Inputs -> Outputs:** `(natural, total, dc)` -> degree enum.

**Implementation surface:** `deterministic`.

**Key dependencies:** `PF2E_MVP_SUBSET.md` degree rules.

**Success signal:** Boundary tests cover DC, DC +/- 10, natural 1, and natural
20 adjustments.

### 2.2 `seeded-roll-resolution`

**Purpose:** Resolve all die rolls through DiceService with replayable seeds
and complete roll log entries.

**Inputs -> Outputs:** `(roll_request, seed)` -> `RollResult`.

**Implementation surface:** `deterministic`.

**Key dependencies:** DiceService, `STATE_SCHEMA.md` `RollResult`.

**Success signal:** Same seed and same ordered inputs reproduce exact results.

### 2.3 `skill-check-resolution`

**Purpose:** Resolve a skill or perception check against a fixed DC.

**Inputs -> Outputs:** `CheckProposal(kind="skill")` -> `CheckResult`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `degree-of-success`, `seeded-roll-resolution`,
`CharacterSheet.skills`.

**Success signal:** Fixture checks produce expected totals, degrees, and roll
log entries.

### 2.4 `strike-resolution`

**Purpose:** Resolve a Strike against target AC and produce hit, miss, critical
hit, damage, and state deltas.

**Inputs -> Outputs:** `(attacker, target, attack_profile)` -> `CheckResult`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `degree-of-success`, DiceService, combatant HP state,
first-slice creature records.

**Success signal:** Strike fixtures cover miss, hit, critical hit, and target
reduced to 0 HP.

### 2.5 `initiative-resolution`

**Purpose:** Roll and sort initiative entries at combat start.

**Inputs -> Outputs:** `(combatants, default_skill)` -> `CombatState`
initiative fields.

**Implementation surface:** `deterministic`.

**Key dependencies:** DiceService, `CharacterSheet.perception_modifier`,
creature perception modifiers.

**Success signal:** Initiative order is stable under seeded replay and ties use
the documented tie-breaker.

### 2.6 `action-economy-tracking`

**Purpose:** Track three actions and one reaction per combatant per round.

**Inputs -> Outputs:** `(combat_state, declared_action)` -> updated
`CombatState` or validation error.

**Implementation surface:** `deterministic`.

**Key dependencies:** `STATE_SCHEMA.md` `CombatState`.

**Success signal:** Tests reject a fourth action and refresh action counts at
the correct round boundary.

### 2.7 `theater-positioning`

**Purpose:** Apply and validate abstract theater-of-mind position changes.

**Inputs -> Outputs:** `(combat_state, movement_action)` -> position delta.

**Implementation surface:** `deterministic`.

**Key dependencies:** `PF2E_MVP_SUBSET.md` position tags.

**Success signal:** `Stride` and `Step` transitions produce valid position
deltas and reject unsupported map-style coordinates.

### 2.8 `condition-application`

**Purpose:** Apply, tick, and remove supported conditions.

**Inputs -> Outputs:** `(target_state, condition_effect)` -> `StateDelta`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `STATE_SCHEMA.md` condition model, full MVP condition
list.

**Success signal:** Condition fixtures apply expected modifiers and expire at
the correct time. May be stubbed in the first vertical slice.

### 2.9 `encounter-budget-validation`

**Purpose:** Validate an Oracle-proposed encounter against PF2e XP budget
tables.

**Inputs -> Outputs:** `(party_level, difficulty, creatures)` ->
`EncounterBudget`.

**Implementation surface:** `deterministic`.

**Key dependencies:** local XP budget data, creature records.

**Success signal:** Moderate level-1 fixture validates to the expected budget;
over-budget encounter is rejected.

### 2.10 `retcon-aware-replay`

**Purpose:** Recompute mechanical state from canonical non-retconned turns.

**Inputs -> Outputs:** `(checkpoint, roll_log, state_deltas)` -> rebuilt
mechanics state.

**Implementation surface:** `deterministic`.

**Key dependencies:** `PERSISTENCE_SPEC.md`, DiceService, checkpoint schema.

**Success signal:** Replay after a retconned turn reproduces the expected state
and ignores retconned rolls.

## 3. First-Slice Required Skills

The first vertical slice requires:

- `degree-of-success`
- `seeded-roll-resolution`
- `skill-check-resolution`
- `strike-resolution`
- `initiative-resolution`
- `action-economy-tracking`
- `theater-positioning`

`condition-application`, `encounter-budget-validation`, and
`retcon-aware-replay` may start as interface stubs.
