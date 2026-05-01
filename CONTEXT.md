# Coding Harness Context

This file is for coding-harness routing only. It is not SagaSmith
product/runtime context, and SagaSmith runtime agents must not read it as game
or campaign context.

## Context Map

- SagaSmith product/runtime context: `docs/sagasmith/SAGASMITH_CONTEXT.md`
- Coding-harness architecture-review backlog: `.kilo/ARCHITECTURE-DEEPENING-BACKLOG.md`

## Separation Rule

Keep Kilo, GSD, skill, planning-agent, and architecture-review notes out of
SagaSmith product/runtime context. Keep SagaSmith in-world runtime context out
of coding-harness files unless a harness task explicitly needs to inspect it.
