# SagaSmith - Persistence and Checkpoint Specification

**Status:** Draft  
**Audience:** Implementers of LangGraph checkpointing, ArchivistAgent,
session storage, vault sync, and recovery commands.  
**Companion specs:** `GAME_SPEC.md`, `STATE_SCHEMA.md`, `VAULT_SCHEMA.md`.

## 1. Purpose

SagaSmith must survive quit, crash, and network failure without losing a
completed turn. This document defines write ordering, transaction boundaries,
and rebuild behavior for the first implementation.

## 2. Storage Layers

Authoritative layers:

- SQLite campaign DB: profiles, settings, transcripts, roll logs, turn records,
  LangGraph checkpoints, cost logs.
- Master vault: canonical campaign markdown, including GM-only content.

Derived layers:

- Player vault projection.
- SQLite FTS5 index.
- LanceDB embeddings.
- NetworkX graph.

Derived layers must be rebuildable from SQLite plus the master vault.

## 3. Turn Lifecycle

Each player turn has these phases:

1. `input_received`
2. `pre_narration_checkpoint`
3. `mechanics_resolved`
4. `narration_streaming`
5. `turn_close_persisting`
6. `player_vault_synced`
7. `prompt_returned`

A turn is considered complete only after `turn_close_persisting` succeeds.
If player vault sync fails, the turn remains complete and the UI surfaces a
repair warning.

## 4. Write Ordering

Turn-close writes must occur in this order:

1. Begin SQLite transaction.
2. Append transcript records, including player input and generated narration.
3. Append roll logs.
4. Append LLM call logs with secrets redacted.
5. Store applied `StateDelta`s.
6. Store LangGraph checkpoint through the SQLite saver.
7. Commit SQLite transaction.
8. Write or update master vault pages using atomic file replacement.
9. Upsert derived indices: FTS5, LanceDB, NetworkX.
10. Sync player vault projection.

If step 1-7 fails, the turn is not complete and must be retried or rolled back
to the last checkpoint.

If step 8 fails, the turn is marked `needs_vault_repair`; derived sync does not
run.

If step 9 or 10 fails, the turn is complete and `ttrpg vault rebuild` or
`ttrpg vault sync` must be able to repair the campaign.

## 5. Checkpoints

Checkpoint rules:

- A pre-narration checkpoint is written after mechanics are resolved but
  before Orator streaming starts.
- A final checkpoint is written during SQLite commit at turn close.
- Checkpoints contain compact graph state, not full vault body text.
- Checkpoints are versioned with app semver and schema version.

Resume behavior:

- If the last turn has a final checkpoint, resume at the next prompt.
- If only a pre-narration checkpoint exists, resume by rerunning narration or
  offering to discard the incomplete turn.
- If SQLite and vault disagree, SQLite wins for transcript/roll history and the
  master vault is repaired from recorded state deltas where possible.

## 6. Atomic Vault Writes

Every vault write uses:

1. Write complete content to a temp file in the target directory.
2. Flush and close.
3. Replace target with `os.replace()`.
4. Re-read and validate YAML frontmatter.

Partial files must never be visible as canonical vault pages.

## 7. Rebuild Commands

`ttrpg vault rebuild`:

- Re-reads the master vault.
- Rebuilds NetworkX graph.
- Rebuilds FTS5 index.
- Rebuilds LanceDB embeddings.
- Validates wikilinks and YAML frontmatter.

`ttrpg vault sync`:

- Reprojects master vault to player vault.
- Strips GM-only content.
- Regenerates `index.md`.
- Appends missing `log.md` entries when possible.

## 8. Retcon

`/retcon` removes the last completed turn from canon only after confirmation.

Minimum behavior:

- Mark the turn as `retconned` in SQLite.
- Apply inverse state deltas when available.
- Rebuild master-vault affected pages from prior canonical state.
- Rebuild derived indices.
- Resync player vault.

If inverse deltas are not available, the command must stop and ask the player
to choose a manual correction path.

## 9. First Vertical Slice

The first implementation needs:

- SQLite campaign DB.
- LangGraph SQLite checkpoint saver.
- Transcript table.
- Roll log table.
- Atomic master-vault page write.
- Player vault projection for known pages.
- `ttrpg vault rebuild` may initially validate only YAML and wikilinks.

LanceDB and NetworkX may be stubbed behind interfaces until Archivist memory
retrieval is implemented.
