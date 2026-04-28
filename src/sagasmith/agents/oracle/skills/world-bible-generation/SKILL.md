---
name: world-bible-generation
description: Create the initial hidden campaign world bible from onboarding records.
allowed_agents: [oracle]
implementation_surface: prompted
first_slice: false
success_signal: Generated world bible validates against schema and avoids player hard limits.
---
# World Bible Generation

## When to Activate
On the first play-phase Oracle invocation after onboarding has produced
`PlayerProfile`, `ContentPolicy`, and `HouseRules`, when `world_bible` is absent.

## Inputs
- `PlayerProfile`
- `ContentPolicy`
- `HouseRules`

## Output
- `WorldBible`

## Procedure
Use the versioned prompt module at `sagasmith.prompts.oracle.world_bible_generation`
and call the configured LLM client with structured JSON output. Validate the response
against `WorldBible` before storing it in graph state.

## Failure Handling
Schema failures use `invoke_with_retry`. Budget exhaustion raises `BudgetStopError`
through the standard runtime path so setup fails loudly rather than continuing with
partial world data.
