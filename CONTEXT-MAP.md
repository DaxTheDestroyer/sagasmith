# Context Map

SagaSmith intentionally separates coding-harness context from SagaSmith
product/runtime context.

## Contexts

- `LAYOUT.md` - visual two-tree map of dev harness vs SagaSmith runtime.
- `CONTEXT.md` - coding-harness routing only. This file exists for tools that
  probe for a repository-root context file.
- `docs/sagasmith/SAGASMITH_CONTEXT.md` - SagaSmith-owned product/runtime context,
  domain vocabulary, and internal runtime concepts.
- `.kilo/ARCHITECTURE-DEEPENING-BACKLOG.md` - Kilo architecture-review output
  and deepening opportunities. This is not SagaSmith product/runtime context.

## Reader Rules

- Coding-harness agents may read `CONTEXT.md` and this map to find the right
  context file for a task.
- SagaSmith runtime agents must use SagaSmith-owned specs and runtime state,
  not Kilo harness files.
- Architecture-review notes belong under `.kilo/` unless they are promoted into
  an accepted SagaSmith spec or ADR.
