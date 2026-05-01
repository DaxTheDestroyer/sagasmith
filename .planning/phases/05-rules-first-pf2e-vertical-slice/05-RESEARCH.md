# Phase 5 — Rules-First PF2e Vertical Slice Research

**Status:** Complete
**Date:** 2026-04-27

## Phase Goal

User can complete first-slice PF2e mechanics with a visible character sheet, dice overlay, replayable rolls, and no LLM-authored math.

## Canonical Sources

- `docs/sagasmith/PF2E_MVP_SUBSET.md` controls first-slice mechanics scope.
- `docs/sagasmith/STATE_SCHEMA.md` defines `CharacterSheet`, `CombatState`, `CheckProposal`, `CheckResult`, and `RollResult`.
- `docs/sagasmith/GAME_SPEC.md` defines Textual TUI dice UX, status panel, and no-LLM-math boundaries.
- `.planning/phases/05-rules-first-pf2e-vertical-slice/05-UI-SPEC.md` defines approved reveal overlay, `/sheet`, status, and combat display contracts.

## Existing Codebase Interfaces

- `src/sagasmith/services/dice.py`: `DiceService.roll_d20(purpose, actor_id, modifier, roll_index, dc)` creates deterministic `RollResult` with stable `roll_id`.
- `src/sagasmith/services/pf2e.py`: `compute_degree(natural, total, dc)` already implements PF2e natural 1/20 adjustment and boundaries.
- `src/sagasmith/schemas/mechanics.py`: Pydantic models exist for `CharacterSheet`, `CombatState`, `CheckProposal`, `RollResult`, `CheckResult`.
- `src/sagasmith/tui/commands/control.py`: `/sheet`, `/inventory`, `/map` are Phase 5 replacement points.
- `src/sagasmith/agents/rules_lawyer/node.py`: current trigger parser is explicitly marked for Phase 5 replacement.
- `src/sagasmith/graph/routing.py`: combat currently routes to `END`; Phase 5 owns combat sub-routing.
- `src/sagasmith/tui/widgets/status_panel.py`: status already renders HP, conditions, quest, location, clock, and last three rolls.

## Technical Approach

1. Extend deterministic mechanics with local first-slice data and pure services rather than LLM-authored math.
2. Keep `DiceService` and `compute_degree` as the roll/math primitives; add higher-level skill, initiative, strike, and combat functions around them.
3. Persist/append roll log entries from structured `RollResult`/`CheckResult` data; UI audit cues must use persisted `roll_id`, not a UI-only id.
4. Replace Phase 3 TUI stubs by rendering structured `CharacterSheet`, roll summaries, and combat state as plain terminal text.
5. Route graph play/combat through deterministic RulesLawyer behavior; Phase 6 may later add AI proposal generation, but Phase 5 must work without paid calls.

## Security and Safety Constraints

- Trust boundary: player input to RulesLawyer intent parsing. Accept only first-slice deterministic commands/intents; unsupported actions must fail closed without rolls.
- Trust boundary: structured mechanics to TUI transcript. Render from Pydantic models and keep Rich markup disabled for untrusted narration lines.
- Trust boundary: graph state/checkpoints. Do not store API keys or auth headers in mechanics logs, checkpoints, or transcript lines.
- No LLM agent may produce modifiers, DCs, damage, HP deltas, action counts, or degrees.

## Validation Architecture

Blocking checks for this phase:

- Unit: `uv run pytest tests/services/test_pf2e_degree.py tests/services/test_dice.py tests/services/test_rules_engine.py tests/services/test_combat_engine.py -q`
- Schema/data: `uv run pytest tests/schemas/test_mechanics_models.py tests/rules/test_first_slice_data.py -q`
- TUI: `uv run pytest tests/tui/test_sheet_command.py tests/tui/test_dice_overlay.py tests/tui/test_combat_status.py -q`
- Graph/integration: `uv run pytest tests/agents/test_rules_lawyer_phase5.py tests/integration/test_rules_first_vertical_slice.py -q`
- Quality: `uv run ruff check src tests && uv run pyright src tests`

## Out of Scope for Phase 5

- Spellcasting, Raise a Shield, Demoralize, Recall Knowledge, Trip, Grapple.
- Tactical grid, maps with coordinates, or more than two enemies.
- AI-generated scene planning or narration. Phase 6 owns AI GM story loop.
- `/retcon` rollback confirmation. Phase 8 owns rollback.
