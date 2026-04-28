---
name: campaign-seed-generation
description: Produce 3-5 opening plot hooks and one selected seed arc from the world bible.
allowed_agents: [oracle]
implementation_surface: prompted
first_slice: false
success_signal: Hook fixtures produce distinct hooks aligned with player preferences.
---
# Campaign Seed Generation

## When to Activate
Immediately after `world-bible-generation` succeeds for a new play-phase campaign,
or on re-entry when `world_bible` exists and `campaign_seed` is absent.

## Inputs
- `WorldBible`
- `PlayerProfile`

## Output
- `CampaignSeed`

## Procedure
Use the versioned prompt module at `sagasmith.prompts.oracle.campaign_seed_generation`
and call the configured LLM client with structured JSON output. Validate the response
against `CampaignSeed` before storing it in graph state.

## Failure Handling
Schema failures use `invoke_with_retry`. Budget exhaustion raises `BudgetStopError`
through the standard runtime path so setup fails loudly rather than storing partial
campaign seed data.
