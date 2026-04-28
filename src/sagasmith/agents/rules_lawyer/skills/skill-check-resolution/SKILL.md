---
name: skill-check-resolution
description: Convert player skill-check intent to a CheckProposal and resolve it against deterministic rules services.
allowed_agents: [rules_lawyer]
implementation_surface: hybrid
first_slice: true
success_signal: Valid CheckResult with auditable roll, deterministic modifier, and deterministic degree of success.
---
# Skill Check Resolution

## When to Activate
When player input declares or implies a first-slice skill/perception check, including explicit syntax such as `roll athletics dc 15` and natural language such as "I climb the ledge".

## Inputs
- `CheckProposal` with `kind="skill"`, actor, stat, deterministic modifier, deterministic DC, and reason.
- `CharacterSheet` for supported skill and perception modifiers.
- Scene context with deterministic DC hints when available; otherwise the Phase 6 first-slice fallback DC is used.

## Output
- `CheckResult` containing the auditable `RollResult`, degree of success, effects, and state deltas.

## Procedure
1. Resolve intent with deterministic patterns first; use LLM fallback only when no pattern matches and an LLM client is injected.
2. Treat LLM output as classification only. Never accept LLM-authored modifiers, DCs, damage, HP changes, or degrees.
3. Build and validate `CheckProposal` via `RulesEngine` from the `CharacterSheet` and deterministic DC source.
4. Resolve the roll through `RulesEngine.resolve_check`, which owns the seeded die roll, modifier lookup, total, and degree of success.

## Deterministic Handler
Composes:
- `sagasmith.services.intent_resolution.resolve_intents`
- `sagasmith.agents.rules_lawyer.intent_to_proposal.proposals_from_candidates`
- `sagasmith.services.rules_engine.RulesEngine.resolve_check`

See rules-lawyer-skills.md §2.3 for the original check contract.

## Failure Handling
If the character sheet lacks the requested stat, or input names an unsupported first-slice action, return a visible `Rules error:` message without rolling. If intent LLM budget is exhausted, fall back to deterministic-only routing and prompt the player to use explicit `/check athletics 15` syntax.
