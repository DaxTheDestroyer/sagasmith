---
name: onboarding-phase-wizard
description: Drive the 9-phase onboarding wizard (story preferences, content policy, house rules, budget, dice UX, campaign length, character mode) to produce validated PlayerProfile, ContentPolicy, and HouseRules.
allowed_agents: [onboarding]
implementation_surface: deterministic
first_slice: true
success_signal: OnboardingStore.commit() produces a valid triple; re-runs are idempotent.
---
# Onboarding Phase Wizard

## When to Activate
When `state.player_profile`, `state.content_policy`, or `state.house_rules` is None.

## Procedure
The wizard was delivered in Plan 03-02. This SKILL.md documents the existing
state machine + SQLite-backed store; the onboarding node in the graph calls
into `sagasmith.onboarding.store.OnboardingStore` to advance the wizard.

## Deterministic Handler
Module: `sagasmith.onboarding.store`.
Class: `OnboardingStore` (state machine + atomic commit).

## Failure Handling
Validation errors surface on `.commit()`; partial state stays in the store
until the user completes or abandons.
