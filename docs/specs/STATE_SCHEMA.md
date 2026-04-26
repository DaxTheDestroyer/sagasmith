# SagaSmith - Runtime State Schema

**Status:** Draft  
**Audience:** Implementers of the LangGraph state, service boundaries, and
JSON/Pydantic models.  
**Companion specs:** `GAME_SPEC.md`, `ADR-0001-orchestration-and-skills.md`,
`VAULT_SCHEMA.md`.

## 1. Purpose

This document defines the first implementation contract for objects passed
between SagaSmith agents. It is intentionally narrower than the full product
vision: enough to build and test the first vertical slice without guessing at
field names or ownership boundaries.

All records below should be implemented as Pydantic models. Models that cross
an LLM boundary must also emit JSON Schema for validation and prompt/tool
contracts.

## 2. Naming and IDs

- `campaign_id`, `session_id`, `turn_id`, `scene_id`, and entity IDs are
  stable strings.
- Vault-backed entity IDs match vault filenames without `.md`
  (`npc_marcus_innkeeper`).
- Runtime-only IDs use a short type prefix plus monotonic or random suffix
  (`turn_000014`, `roll_000031`).
- Timestamps are stored as ISO 8601 strings with timezone where real-world
  time matters.

## 3. Graph State

`SagaState` is the LangGraph state object. It carries references and compact
payloads, not full vault contents.

Required fields:

| Field | Type | Owner | Notes |
|---|---|---|---|
| `campaign_id` | `str` | CLI/bootstrap | Stable campaign identity. |
| `session_id` | `str` | Session manager | Current real play session. |
| `turn_id` | `str` | Graph runtime | Incremented once per player turn. |
| `phase` | enum | Graph routing | `onboarding`, `character_creation`, `play`, `combat`, `paused`, `session_end`. |
| `player_profile` | `PlayerProfile | None` | Onboarding | Required before play. |
| `content_policy` | `ContentPolicy | None` | Onboarding/SafetyGuard | Required before play. |
| `house_rules` | `HouseRules | None` | Onboarding | Required before play. |
| `character_sheet` | `CharacterSheet | None` | Character creation | Required before first scene. |
| `session_state` | `SessionState` | Graph runtime | Current scene, clock, quest, and transcript refs. |
| `combat_state` | `CombatState | None` | RulesLawyer | Non-null only during combat. |
| `pending_player_input` | `str | None` | TUI | Raw command/action for current turn. |
| `memory_packet` | `MemoryPacket | None` | Archivist | Token-bounded context for Oracle/Orator. |
| `scene_brief` | `SceneBrief | None` | Oracle | Current scene plan. |
| `check_results` | `list[CheckResult]` | RulesLawyer | Mechanical outcomes this turn. |
| `state_deltas` | `list[StateDelta]` | RulesLawyer/Archivist | Applied or pending state changes. |
| `pending_conflicts` | `list[CanonConflict]` | Archivist | Consumed by Oracle next turn. |
| `safety_events` | `list[SafetyEvent]` | SafetyGuard | `/pause`, `/line`, redline rewrites. |
| `cost_state` | `CostState` | CostGovernor | Budget, usage, warnings. |

## 4. Player Configuration

### 4.1 `PlayerProfile`

Required fields:

- `genre: list[str]`
- `tone: list[str]`
- `touchstones: list[str]`
- `pillar_weights: dict[str, float]`
- `pacing: "slow" | "medium" | "fast"`
- `combat_style: "theater_of_mind"` for MVP
- `dice_ux: "auto" | "reveal" | "hidden"`
- `campaign_length: "one_shot" | "arc" | "open_ended"`
- `character_mode: "guided" | "player_led" | "pregenerated"`
- `death_policy: "hardcore" | "heroic_recovery" | "retire_and_continue"`
- `budget: BudgetPolicy`

Validation:

- `pillar_weights` must include `combat`, `exploration`, `social`, `puzzle`.
- Pillar values must sum to `1.0` within `0.01`.
- MVP rejects any `combat_style` other than `theater_of_mind`.

### 4.2 `ContentPolicy`

Required fields:

- `hard_limits: list[str]`
- `soft_limits: dict[str, "fade_to_black" | "avoid_detail" | "ask_first"]`
- `preferences: list[str]`

### 4.3 `HouseRules`

Required fields:

- `dice_ux`
- `initiative_visible: bool`
- `allow_retcon: bool`
- `auto_save_every_turn: bool`
- `session_end_trigger: "player_command_or_budget"`

## 5. Narrative State

### 5.1 `SessionState`

Required fields:

- `current_scene_id: str | None`
- `current_location_id: str | None`
- `active_quest_ids: list[str]`
- `in_game_clock: GameClock`
- `turn_count: int`
- `transcript_cursor: str | None`
- `last_checkpoint_id: str | None`

### 5.2 `SceneBrief`

Required fields:

- `scene_id: str`
- `intent: str`
- `location: str | None`
- `present_entities: list[str]`
- `beats: list[str]`
- `success_outs: list[str]`
- `failure_outs: list[str]`
- `pacing_target: PacingTarget`
- `callbacks_seeded: list[str] = []`
- `callbacks_payoff_candidates: list[str] = []`
- `mechanical_triggers: list[MechanicalTrigger] = []`
- `content_warnings: list[str] = []`

`SceneBrief` is a plan, not player-facing narration. Orator is the only agent
allowed to render prose directly to the player.

### 5.3 `MemoryPacket`

Required fields:

- `token_cap: int`
- `summary: str`
- `entities: list[MemoryEntityRef]`
- `recent_turns: list[str]`
- `open_callbacks: list[str]`
- `retrieval_notes: list[str]`

Validation:

- Estimated tokens must not exceed `token_cap`.
- Every entity reference must map to an existing vault page or be explicitly
  marked as provisional.

## 6. Mechanics State

### 6.1 `CharacterSheet`

The MVP `CharacterSheet` should support one level-1 pregenerated PC first,
then expand to guided creation.

Required fields:

- `id: str`
- `name: str`
- `level: int`
- `ancestry: str`
- `background: str`
- `class_name: str`
- `abilities: dict[str, int]`
- `proficiencies: dict[str, ProficiencyRank]`
- `max_hp: int`
- `current_hp: int`
- `armor_class: int`
- `perception_modifier: int`
- `saving_throws: dict[str, int]`
- `skills: dict[str, int]`
- `attacks: list[AttackProfile]`
- `inventory: list[InventoryItem]`
- `conditions: list[ConditionInstance]`

### 6.2 `CombatState`

Required fields:

- `encounter_id: str`
- `round_number: int`
- `active_combatant_id: str`
- `initiative_order: list[InitiativeEntry]`
- `combatants: list[CombatantState]`
- `positions: dict[str, "close" | "near" | "far" | "behind_cover"]`
- `action_counts: dict[str, int]`
- `reaction_available: dict[str, bool]`

### 6.3 `CheckProposal`

Required fields:

- `id: str`
- `reason: str`
- `kind: "skill" | "attack" | "save" | "initiative" | "flat"`
- `actor_id: str`
- `target_id: str | None`
- `stat: str`
- `modifier: int`
- `dc: int | None`
- `secret: bool`

### 6.4 `CheckResult`

Required fields:

- `proposal_id: str`
- `roll_result: RollResult`
- `degree: "critical_success" | "success" | "failure" | "critical_failure"`
- `effects: list[Effect]`
- `state_deltas: list[StateDelta]`

### 6.5 `RollResult`

Required fields:

- `roll_id: str`
- `seed: str`
- `die: str`
- `natural: int`
- `modifier: int`
- `total: int`
- `dc: int | None`
- `timestamp: str`

## 7. State Deltas and Conflicts

### 7.1 `StateDelta`

Required fields:

- `id: str`
- `source: "rules" | "oracle" | "archivist" | "safety" | "user"`
- `path: str`
- `operation: "set" | "increment" | "append" | "remove"`
- `value: object`
- `reason: str`

All deltas must be serializable and replayable. Apply order is the list order
stored in `SagaState.state_deltas`.

### 7.2 `CanonConflict`

Required fields:

- `id: str`
- `entity_id: str`
- `asserted_fact: str`
- `canonical_fact: str`
- `category: "retcon_intent" | "pc_misbelief" | "narrator_error"`
- `severity: "minor" | "major"`
- `recommended_resolution: str`

## 8. Safety and Cost

### 8.1 `SafetyEvent`

Required fields:

- `id: str`
- `turn_id: str`
- `kind: "pause" | "line" | "soft_limit_fade" | "post_gate_rewrite" | "fallback"`
- `policy_ref: str | None`
- `action_taken: str`

### 8.2 `CostState`

Required fields:

- `session_budget_usd: float`
- `spent_usd_estimate: float`
- `tokens_prompt: int`
- `tokens_completion: int`
- `warnings_sent: list["70" | "90"]`
- `hard_stopped: bool`

## 9. First Vertical Slice Minimum

The first code milestone only needs these models fully operational:

- `SagaState`
- `PlayerProfile`
- `ContentPolicy`
- `HouseRules`
- `SessionState`
- `SceneBrief`
- `MemoryPacket`
- `CharacterSheet`
- `CheckProposal`
- `CheckResult`
- `RollResult`
- `StateDelta`
- `CostState`

Other models may exist as stubs if they validate, serialize, and round-trip
through a LangGraph checkpoint.
