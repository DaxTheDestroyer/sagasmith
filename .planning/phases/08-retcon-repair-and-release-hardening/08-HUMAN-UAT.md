---
status: partial
phase: 08-retcon-repair-and-release-hardening
source: [08-VERIFICATION.md]
started: 2026-04-29T11:56:16Z
updated: 2026-04-29T11:56:16Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. TUI /retcon visual flow
expected: Candidate list appears with turn IDs and summaries; preview shows affected turns, vault outputs, effects, and exact token instruction; success message appears concise and does not contain removed canon content; post-retcon narration/mechanics display is consistent.
result: [pending]

### 2. make release-gate composite execution
expected: All six gates (lint, format-check, typecheck, test, MVP smoke, secret-scan) execute in order on a make-capable environment; MVP smoke 8/8 passes; secret scan passes; overall exit code 0.
result: [pending]

### 3. Pre-existing repository-wide quality gate alignment
expected: ruff format --check reports 0 reformattable files; pyright reports 0 errors; pytest -q reports 0 failures.
result: [pending]

### 4. /retcon candidate list UX with real campaign data
expected: Recent eligible completed turns appear; summaries are concise (<160 chars); the player cannot accidentally retcon without explicit confirmation.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
