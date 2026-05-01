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
