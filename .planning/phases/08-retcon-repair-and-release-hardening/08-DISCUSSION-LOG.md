# Phase 8: Retcon, Repair, and Release Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 08-retcon-repair-and-release-hardening
**Areas discussed:** Retcon semantics, Confirmation UX, Canonical exclusion, Release gates

---

## Retcon Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Latest complete | Target the newest turn with canonical completed status, ignoring discarded/retried/retconned/non-complete repair states. | |
| Latest visible | Target whatever the player most recently saw, even if the turn has repair warnings or non-standard status. | |
| User chooses | Require the user to choose from recent turns before any retcon can proceed. | yes |

**User's choice:** User chooses
**Notes:** `/retcon` should not silently target the latest turn; the player selects from eligible recent completed turns.

| Option | Description | Selected |
|--------|-------------|----------|
| Mark retained | Keep rows/files for audit and mark the turn retconned; canonical reads filter it out. | yes |
| Delete rows | Remove retconned records to simplify reads, sacrificing auditability and recovery traceability. | |
| Archive copy | Move retconned data to a separate archive table/folder, then remove it from active stores. | |

**User's choice:** Mark retained
**Notes:** Audit data remains available but is not canonical.

| Option | Description | Selected |
|--------|-------------|----------|
| Checkpoint rewind | Rewind graph state to the pre-turn or prior-final checkpoint, then repair/rebuild derived outputs. | yes |
| Inverse deltas | Compute reverse state deltas and apply them directly to current state. | |
| Manual only | Do not automate state rollback; retcon records intent and prompts user/developer repair steps. | |

**User's choice:** Checkpoint rewind
**Notes:** Checkpoints are the primary rollback source; derived outputs should be repaired/rebuilt afterward.

| Option | Description | Selected |
|--------|-------------|----------|
| Block retcon | Refuse the retcon with clear repair guidance rather than guessing at canon. | yes |
| Narrative only | Allow a retcon note while leaving mechanical/vault state unchanged. | |
| Best effort | Proceed with available data and warn that manual repair may be needed. | |

**User's choice:** Block retcon
**Notes:** Missing safe rollback data is a hard stop.

---

## Confirmation UX

| Option | Description | Selected |
|--------|-------------|----------|
| Recent-turn picker | `/retcon` shows recent completed turns and asks the player to pick one before confirmation. | yes |
| Immediate latest | `/retcon` immediately proposes the latest completed turn without a picker. | |
| Command argument | Player must type a turn identifier, like `/retcon turn-123`. | |

**User's choice:** Recent-turn picker
**Notes:** The picker is the default start of the retcon flow.

| Option | Description | Selected |
|--------|-------------|----------|
| Typed phrase | Require typing a phrase like `retcon turn` or the turn ID before rollback starts. | yes |
| Yes button | A simple confirm/cancel prompt or modal is enough. | |
| Double prompt | Ask once to select and once again to confirm consequences. | |

**User's choice:** Typed phrase
**Notes:** Confirmation must be explicit enough to avoid accidental canon rollback.

| Option | Description | Selected |
|--------|-------------|----------|
| Summary plus effects | Show turn summary, affected mechanics/vault/memory outputs, and that retconned data remains audit-only. | yes |
| Short warning | Show a concise warning and ask for confirmation without enumerating affected records. | |
| Full audit diff | Show detailed state delta, vault page, transcript, and checkpoint changes before confirmation. | |

**User's choice:** Summary plus effects
**Notes:** Show consequences without requiring a full low-level diff.

| Option | Description | Selected |
|--------|-------------|----------|
| Return to safe prompt | Rewind to the prior safe prompt/checkpoint and show a concise retcon completion message. | yes |
| Open repair flow | Immediately route into vault/derived-index repair commands before continuing play. | |
| Exit session | Complete the retcon, save, and exit so the next launch resumes from the repaired state. | |

**User's choice:** Return to safe prompt
**Notes:** Successful automated retcon returns the player to play at the safe checkpoint.

---

## Canonical Exclusion

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude everywhere | Any canonical read excludes retconned turns unless explicitly asking for audit/debug data. | yes |
| Exclude memory only | Only summaries and memory packets exclude retconned turns; lower-level replay still sees them. | |
| Context-specific | Each subsystem decides whether retconned turns matter. | |

**User's choice:** Exclude everywhere
**Notes:** Retconned turns are never canonical by default.

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical helpers | Add shared repository/query helpers for canonical turns so tests can enforce one path. | yes |
| Local filters | Each caller adds `status != retconned` style filters directly where needed. | |
| Database view | Create a SQLite canonical-turn view and route canonical reads through it. | |

**User's choice:** Canonical helpers
**Notes:** Avoid filter drift across replay, memory, vault, and smoke code paths.

| Option | Description | Selected |
|--------|-------------|----------|
| Rebuild canonical only | Rebuild player/master canonical outputs from non-retconned sources; retconned artifacts remain audit-only. | yes |
| Keep visible note | Player vault includes a note that a retcon occurred, without GM-only details. | |
| Manual cleanup | Retcon marks data, but user must run repair/cleanup separately to remove projected content. | |

**User's choice:** Rebuild canonical only
**Notes:** Derived/vault rebuilds use non-retconned sources.

| Option | Description | Selected |
|--------|-------------|----------|
| Brief log entry | Keep a spoiler-safe player-visible log entry that a retcon occurred, but no removed canon details. | yes |
| Hidden audit only | Only internal audit/debug surfaces show retcon events; player-facing memory has no marker. | |
| Full player note | Player can see a fuller explanation of what changed and why. | |

**User's choice:** Brief log entry
**Notes:** Player-visible retcon marker is allowed if spoiler-safe and detail-free.

---

## Release Gates

| Option | Description | Selected |
|--------|-------------|----------|
| Full MVP path | One no-paid-call path covers init, configure, onboard, play skill challenge, play combat, quit, resume. | yes |
| Critical slices | Separate smoke checks for init/configure/onboard/rules/resume, not one continuous flow. | |
| Existing smoke plus tests | Keep smoke fast and rely on unit/integration tests for the full path. | |

**User's choice:** Full MVP path
**Notes:** QA-08 must prove the complete MVP flow, not just isolated slices.

| Option | Description | Selected |
|--------|-------------|----------|
| Layered smoke | Use in-process tests for detail plus at least one `uv run sagasmith ...` shell path to prove entrypoint/install behavior. | yes |
| In-process only | Use Python test harnesses only for speed and easier fixtures. | |
| Shell only | Drive everything via CLI subprocesses for maximum realism. | |

**User's choice:** Layered smoke
**Notes:** Combine test observability with at least one shell-level local entrypoint proof.

| Option | Description | Selected |
|--------|-------------|----------|
| make release-gate | One command runs lint, format check, type check, unit tests, MVP smoke, and secret scan. | yes |
| pre-commit all | Use `pre-commit run --all-files` as the primary release gate and keep smoke separate. | |
| docs only | Document the command sequence but do not add a wrapper command. | |

**User's choice:** make release-gate
**Notes:** Planner should target a wrapper command in `Makefile`.

| Option | Description | Selected |
|--------|-------------|----------|
| Gitleaks gate | Release gate runs gitleaks/pre-commit secret scan and redaction canary regressions. | yes |
| Redaction only | Rely on project redaction canary tests, not an external gitleaks command. | |
| Optional scan | Secret scan is documented but not release-blocking locally. | |

**User's choice:** Gitleaks gate
**Notes:** Secret scanning is release-blocking alongside redaction canary tests.

---

## the agent's Discretion

- Exact status names, migration numbers, method names, prompt/modal implementation details, and release-gate command internals are left to downstream research/planning as long as the captured decisions are honored.

## Deferred Ideas

- Full LLM-based `canon-conflict-detection` classifier remains deferred.
- `callback-reachability-query`, `master-vault-unlock`, LanceDB activation, and new gameplay breadth remain out of Phase 8 scope.
