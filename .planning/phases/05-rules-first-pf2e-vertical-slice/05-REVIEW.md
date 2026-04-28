---
phase: 05-rules-first-pf2e-vertical-slice
reviewed: 2026-04-28T12:25:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - src/sagasmith/rules/__init__.py
  - src/sagasmith/rules/first_slice.py
  - src/sagasmith/schemas/common.py
  - src/sagasmith/services/dice.py
  - src/sagasmith/services/rules_engine.py
  - src/sagasmith/services/combat_engine.py
  - src/sagasmith/agents/rules_lawyer/node.py
  - src/sagasmith/graph/routing.py
  - src/sagasmith/graph/graph.py
  - src/sagasmith/graph/runtime.py
  - src/sagasmith/tui/app.py
  - src/sagasmith/tui/commands/control.py
  - src/sagasmith/tui/state.py
  - src/sagasmith/tui/widgets/sheet.py
  - src/sagasmith/tui/widgets/dice_overlay.py
  - src/sagasmith/tui/widgets/status_panel.py
  - src/sagasmith/evals/harness.py
  - tests/rules/test_first_slice_data.py
  - tests/services/test_rules_engine.py
  - tests/services/test_combat_engine.py
  - tests/agents/test_rules_lawyer_phase5.py
  - tests/graph/test_routing.py
  - tests/graph/test_graph_bootstrap.py
  - tests/tui/test_sheet_command.py
  - tests/tui/test_dice_overlay.py
  - tests/tui/test_combat_status.py
  - tests/integration/test_rules_first_vertical_slice.py
  - tests/evals/test_rules_first_qa_gate.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-04-28T12:25:00Z  
**Depth:** standard  
**Files Reviewed:** 27  
**Status:** issues_found

## Summary

Reviewed the Phase 5 PLAN/SUMMARY artifacts and the implemented rules, combat, graph, TUI, smoke/eval, and regression-test changes. Targeted regression tests passed (`uv run pytest tests/services/test_combat_engine.py tests/tui/test_combat_status.py tests/integration/test_rules_first_vertical_slice.py -q`, 14 passed), but the review found advisory correctness issues in combat turn enforcement and TUI/status rendering.

## Warnings

### WR-01: Combat actions are not restricted to the active combatant

**File:** `src/sagasmith/services/combat_engine.py:91-94` and `src/sagasmith/agents/rules_lawyer/node.py:89-95`  
**Issue:** `resolve_strike()` validates the actor exists, has actions, and target range is legal, but it never checks `state.active_combatant_id`. `rules_lawyer_node()` always submits the PC as actor, so a player can Strike or move while an enemy is the active combatant, bypassing initiative and turn order.  
**Fix:** Fail closed before action consumption/rolling when the actor is not active, and add a RulesLawyer/integration regression.

```python
def _require_active_turn(state: CombatState, combatant_id: str) -> None:
    if state.active_combatant_id != combatant_id:
        raise ValueError(f"it is {state.active_combatant_id}'s turn, not {combatant_id}'s turn")

# in resolve_strike/move, before _require_actions(...)
_require_active_turn(state, actor_id)
```

### WR-02: Status panel classifies the real PC as an enemy

**File:** `src/sagasmith/tui/widgets/status_panel.py:28`  
**Issue:** Enemy rendering filters with `combatant.id != "pc"`, but Phase 5's actual PC id is `pc_valeros_first_slice`. Real combat states therefore render the PC in the `Enemies:` line alongside enemies. The unit tests use a synthetic `pc` id, so they do not catch the production id mismatch.  
**Fix:** Filter by first-slice enemy identity instead of a hardcoded synthetic PC id, and add a test using `make_first_slice_character().id`.

```python
enemies = [combatant for combatant in combat_state.combatants if combatant.id.startswith("enemy_")]
```

### WR-03: TUI mechanics sync can duplicate historical roll transcript output each turn

**File:** `src/sagasmith/tui/app.py:153-158` and `src/sagasmith/tui/app.py:249-270`  
**Issue:** `_build_play_state()` intentionally carries existing `check_results` forward across sequential inputs, but `_sync_mechanics_from_graph()` resets `_synced_graph_check_result_count` to `0` whenever the turn id changes. On the next player input, it slices from zero and re-renders all persisted historical `CheckResult` entries, duplicating prior compact/reveal roll audit lines in the narration transcript.  
**Fix:** Track rendered roll IDs independently of turn id, or initialize the per-turn counter to the count already present before invoking the new turn so only newly appended results render.

```python
# one possible approach
rendered_ids = getattr(self, "_synced_graph_roll_ids", set())
for result in check_results:
    if result.roll_result.roll_id in rendered_ids:
        continue
    narration.append_line(f"CheckResult: {result.proposal_id}")
    narration.append_line(render_compact_roll_line(result, reason=result.proposal_id))
    narration.append_line(render_reveal_check(result, reason=result.proposal_id))
    rendered_ids.add(result.roll_result.roll_id)
self._synced_graph_roll_ids = rendered_ids
```

---

_Reviewed: 2026-04-28T12:25:00Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
