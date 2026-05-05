# SagaSmith Context

This document belongs to SagaSmith product/runtime design. It is separate from
the coding harness that creates and updates SagaSmith.

Do not store Kilo, GSD, skill, planning-agent, or architecture-review backlog
notes here. Put coding-harness notes in `CONTEXT.md`, `CONTEXT-MAP.md`, or
`.kilo/` files unless they are promoted into an accepted SagaSmith spec or ADR.

## Domain Terms

### Campaign Reference

A user-facing value that identifies a local campaign. It may be a campaign
directory path, a campaign slug, or a display name that can be resolved to one
local campaign directory.

### Provider Runtime

The startup path that turns persisted provider settings into a live LLM adapter
for graph execution. It owns loading `ProviderSettings`, resolving `SecretRef`,
choosing the fake or OpenRouter adapter, and surfacing startup failures without
leaking secrets.

### Canonical Turn History

The canonical read model for completed, non-retconned campaign history. It owns
latest-turn status, recent transcript context, next session number, session-page
source rows, and any query where retconned turns must be excluded by default.

### Turn Start

The construction of a valid play-turn graph state from a campaign, session,
current graph snapshot, and player input. It owns turn ID progression, phase
selection, default first-slice character state, cost state, combat carryover,
and narration/check-result carryover.

### Archivist Turn Plan

The pure Archivist workflow for one turn-close preparation pass. It decides
which memory packet, rolling summary, canon conflicts, visibility promotions,
and vault page writes should be returned to the graph runtime for persistence.

### Session Page Authoring

The deterministic drafting of an end-of-session vault page from Canonical Turn
History. It owns session frontmatter, summary/body formatting, beat extraction,
roll-table formatting, and wikilink-derived session metadata; audited vault
writes remain owned by persistence.

### Scene Planning

The Oracle's planning decision for one play turn. It coordinates campaign-context
generation (world bible + campaign seed), memory packet assembly, player-choice
bypass detection, safety pre-gate routing, fallback and LLM-backed scene-brief
composition, and budget-stop detection into one value: a plain `ScenePlan`
carrying state updates, an optional interrupt intent, pre-gate safety events,
and the list of skills activated. The LangGraph Adapter shim owns wrapping the
interrupt intent into an `InterruptEnvelope` and appending safety events to
graph state.

### Safety Guard

The deterministic and bounded-hybrid safety pass for one play turn. It owns
pre-generation scene-intent routing, inline streaming hard-limit scan,
post-generation prose scan, player-visible safety event construction, and
retry/fallback policy for unsafe narration.

### Rules Turn Resolution

The deterministic Rules Lawyer workflow for one player rules turn. It owns
player-intent classification, first-slice defaults, PF2e check/combat execution,
rules error shaping, combat phase transitions, and narration audit messages.
