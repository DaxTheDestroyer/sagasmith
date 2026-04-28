---
name: scene-rendering
description: Buffered stream-after-classify narrative rendering for completed mechanical resolutions; respects dice UX visibility and never contradicts resolved degree-of-success.
allowed_agents: [orator]
implementation_surface: prompted
first_slice: true
success_signal: Every narration line is player-facing, consistent with mechanics, and respects content policy.
---
# Scene Rendering

## When to Activate
After RulesLawyer has resolved all mechanical checks for the current beat and
the graph has resumed past the orator interrupt.

## Inputs
- **SceneBrief** — Oracle planning artifact (beats, beat_ids, intent, location, entities)
- **CheckResults** — Resolved mechanical checks (degree, effects, damage/HP)
- **MemoryPacket** — Recent campaign context (transcript, entities, callbacks)
- **PlayerProfile** — Dice UX preference, tone, genre, pacing

## Procedure (D-06.1 Buffered Stream-After-Classify)

1. **Build prompt** via `prompts/orator/scene_rendering.py` (per D-06.5).
   Encode `CheckResult` payloads as structured constraint tokens in the user
   prompt with an explicit "do not contradict these mechanical outcomes" instruction.
2. **Budget preflight** per D-06.6.  On `BudgetStopError`, emit fallback narration
   and post `BUDGET_STOP`.
3. **Call `LLMClient.stream(...)`**.  Accumulate tokens into a private buffer
   (``list[str]``).  **Do not write to `pending_narration` yet.**
4. **Inline hard-limit matcher** runs against the running buffer on each token
   (via `SafetyInlineMatcher`).  On a hit, cancel the stream early and jump
   to rewrite.
5. **Post-gate classifier** (`SafetyPostGate`) runs against the buffered text.
6. **Mechanical-consistency audit** (deterministic regex, no LLM) runs against
   the buffered text and the active `CheckResult` list.
7. **Playback** — if all gates pass, emit validated tokens to `pending_narration`
   at a paced rate (30–60 tokens/sec).  The TUI sees stream-like UX.
8. **Rewrite ladder** — if any gate fails, request a rewrite (up to two retries).
   After two failures, emit fallback narration.
9. **Emit `resolved_beat_ids`** per D-06.4 — which beats from the active
   `SceneBrief.beats` this prose advanced.

## Dice UX Modes
- **auto**: Weave roll outcomes seamlessly into narration prose.
- **reveal**: Narrate the attempt, pause for dice overlay, resume with outcome.
- **hidden**: Never name rolls, DCs, modifiers, or mechanical terms.

## Failure Handling
If LLM response fails schema validation or safety post-gate, follow the
two-rewrite ladder.  After two failures, emit safe fallback narration line
and log the event.  On `BudgetStopError`, emit fallback and post `BUDGET_STOP`.
