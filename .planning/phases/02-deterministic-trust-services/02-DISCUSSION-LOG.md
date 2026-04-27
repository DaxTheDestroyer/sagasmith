# Phase 2: Deterministic Trust Services - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 02-deterministic-trust-services
**Areas discussed:** Provider boundary, Secret handling, Cost accounting, Persistence rules boundary

---

## Provider Boundary

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Real OpenRouter calls during verification | Opt-in only | Implement the real client, but default tests/smoke use mocks; live calls require explicit env/keyring setup and opt-in marker/flag. | yes |
| Real OpenRouter calls during verification | Mock only | Build only the protocol and fake client in Phase 2. | |
| Real OpenRouter calls during verification | Required live test | Require at least one real OpenRouter call for verification when credentials exist. | |
| First `LLMClient` coverage | JSON plus streaming | Implement structured JSON and streaming text paths together. | yes |
| First `LLMClient` coverage | JSON first | Implement structured JSON fully; stub streaming. | |
| First `LLMClient` coverage | Protocol plus fakes | Implement protocol, request/response models, and deterministic fakes only. | |
| JSON schema failure behavior | Spec retry ladder | One same-model repair, one cheap-model repair, then fail and log redacted metadata. | yes |
| JSON schema failure behavior | Fail immediately | Reject invalid provider JSON without repair. | |
| JSON schema failure behavior | Flexible repair | Allow multiple repair attempts per use case. | |
| Provider log content | Metadata only | Persist request IDs, model, agent, token/cost/failure metadata, and redacted snippets/hashes, not full bodies. | yes |
| Provider log content | Full redacted bodies | Persist full prompts/responses after redaction. | |
| Provider log content | No bodies ever | Never persist prompt or response text in provider logs. | |

**User's choices:** Opt-in only; JSON plus streaming; Spec retry ladder; Metadata only.
**Notes:** User chose to move to the next area after these decisions.

---

## Secret Handling

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Credential reference types | Keyring and env | Support OS keyring references and environment-variable references only. | yes |
| Credential reference types | Env only first | Simpler developer path, delays keyring behavior. | |
| Credential reference types | Keyring only | Safer packaged default, less convenient for development and CI. | |
| Secret-shaped text in artifacts/logs | Fail closed | Reject write/log records unless secret is replaced with safe redaction marker first. | yes |
| Secret-shaped text in artifacts/logs | Auto redact | Replace detected secrets and continue. | |
| Secret-shaped text in artifacts/logs | Warn only | Emit a warning but continue. | |
| Redaction canary breadth | All trust artifacts | Scan provider logs, cost logs, checkpoints/state dumps, transcripts, SQLite test exports, and smoke output. | yes |
| Redaction canary breadth | Provider logs only | Focus only on provider boundary. | |
| Redaction canary breadth | Logs plus checkpoints | Cover provider logs and checkpoint-like state payloads. | |
| Credential error reporting | Safe typed error | Raise a SagaSmith-owned typed error with provider/ref kind only. | yes |
| Credential error reporting | CLI-style message | Return a user-readable message now. | |
| Credential error reporting | Provider passthrough | Surface provider/keyring exception after redaction. | |

**User's choices:** Keyring and env; Fail closed; All trust artifacts; Safe typed error.
**Notes:** User chose to move to the next area after these decisions.

---

## Cost Accounting

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Missing provider-reported cost | Static table fallback | Use bundled static pricing by provider/model, mark cost approximate. | yes |
| Missing provider-reported cost | Block unknown cost | Refuse paid calls without provider-reported cost. | |
| Missing provider-reported cost | Zero until reported | Record tokens but no cost until provider reports it. | |
| Pre-call budget check | Worst-case estimate | Estimate using prompt tokens plus configured `max_tokens`; block if worst-case exceeds budget. | yes |
| Pre-call budget check | Expected estimate | Estimate likely completion length from historical/static defaults. | |
| Pre-call budget check | Post-call only | Update budget after calls and hard-stop only after overrun. | |
| Warning timing | After crossing | After each cost update, emit each threshold warning exactly once when spend crosses it. | yes |
| Warning timing | Before crossing | Warn before any call estimated to cross a threshold. | |
| Warning timing | Both moments | Warn before crossing and confirm after crossing. | |
| Phase 2 hard stop output | Typed stop result | Return/raise typed budget-stop result with safe user-facing text and cost state. | yes |
| Phase 2 hard stop output | Plain exception | Raise a generic exception. | |
| Phase 2 hard stop output | Fallback transcript | Write a local fallback transcript-like record immediately. | |

**User's choices:** Static table fallback; Worst-case estimate; After crossing; Typed stop result.
**Notes:** User chose to move to the next area after these decisions.

---

## Persistence Rules Boundary

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| PF2e rules scope | Dice and degree | Implement seeded d20/DiceService replay plus degree-of-success math only. | yes |
| PF2e rules scope | Add skill checks | Also implement fixed-DC skill checks now. | |
| PF2e rules scope | Add combat basics | Implement initial Strike/initiative/HP logic now. | |
| Seeded dice replay order | Seed plus index | Campaign/session seed plus ordered roll index and roll purpose. | yes |
| Seeded dice replay order | Per-roll seed | Generate/store a seed for each roll. | |
| Seeded dice replay order | Persist RNG state | Store serialized RNG state between rolls. | |
| Persistence scope | SQLite trust records | Migrations/repositories for turn records, roll logs, state deltas, provider/cost logs, checkpoint references, and transaction ordering; no vault writes yet. | yes |
| Persistence scope | SQLite plus vault stub | Include a placeholder master-vault writer interface. | |
| Persistence scope | Full turn close | Implement SQLite, checkpoint, vault writes, derived-index stubs, and player-vault sync now. | |
| Phase 1 advisory hardening | All relevant | Tighten HP invariant, add `sk-proj-` canary coverage, validate fixture overrides, and keep source pyright strictness visible. | yes |
| Phase 1 advisory hardening | Security only | Fold only redaction/key-pattern hardening. | |
| Phase 1 advisory hardening | Rules only | Fold only HP invariant hardening. | |
| Phase 1 advisory hardening | None now | Do not fold advisory items into Phase 2 unless plans naturally touch files. | |

**User's choices:** Dice and degree; Seed plus index; SQLite trust records; All relevant.
**Notes:** User chose to create context after these decisions.

---

## the agent's Discretion

- Exact module names, repository abstractions, migration tooling, fake-provider shape, static pricing table format, and typed exception/result class names.
- Whether redacted snippets are stored at all, as long as full prompt/response bodies are not stored in Phase 2 provider logs.
- Whether SQLite trust records are exposed only through repositories or also through small service APIs.

## Deferred Ideas

- Fixed-DC skill checks, Strikes, initiative, HP damage, action economy, and combat flow remain Phase 5 work.
- TUI `/budget`, player-facing setup prompts, and budget panels remain Phase 3 work.
- LangGraph interrupts and provider/cost node routing remain Phase 4 work.
- Vault writes, derived indices, player-vault projection, and repair commands remain Phase 7 work.
