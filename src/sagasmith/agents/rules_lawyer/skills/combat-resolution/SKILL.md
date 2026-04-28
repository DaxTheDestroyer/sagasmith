---
name: combat-resolution
description: Convert combat intent to attack, movement, turn, or encounter-start proposals and resolve them through deterministic combat services.
allowed_agents: [rules_lawyer]
implementation_surface: hybrid
first_slice: true
success_signal: Valid combat resolution with auditable CheckResult entries and CombatState updates.
---
# Combat Resolution

## When to Activate
When player input describes first-slice combat mechanics: starting combat, Striking a supported enemy, moving between theater-of-mind position tags, or ending a turn.

## Inputs
- `CheckProposal` for proposal-bearing combat actions such as Strike.
- `CombatState` containing initiative, positions, action counts, reactions, and combatants.
- `CharacterSheet` for the player character's deterministic attacks and modifiers.
- Scene context may classify natural-language intent, but it must not provide math.

## Output
- `CheckResult` for auditable attack/initiative rolls when a roll occurs.
- Updated `CombatState` for HP, position, action-count, and turn changes.

## Procedure
1. Resolve player text with deterministic patterns first; use LLM fallback only to classify action shape when patterns do not match.
2. Ignore any LLM-authored math. Use `CombatEngine` and `RulesEngine` to derive attack modifiers, armor-class DCs, cover adjustments, action consumption, damage, and HP changes.
3. Validate generated proposal-bearing actions against `CheckProposal` before deterministic execution.
4. Return deterministic state updates and roll logs only after service validation succeeds.

## Trust Boundary
LLMs may propose target/action shape only. `CombatEngine` remains the source of truth for legal targets, range, cover AC adjustments, actions, damage rolls, HP deltas, and encounter completion.

## Failure Handling
Unsupported targets, attacks, positions, or unavailable combat state return a visible `Rules error:` message without rolling or consuming actions.
