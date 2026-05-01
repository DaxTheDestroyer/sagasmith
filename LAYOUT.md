# SagaSmith Repo Layout

This file exists so a new contributor (or future-you) can see the boundary
between the two "harnesses" in this repo at a glance.  The canonical rule is
in `AGENTS.md §Hard Context Separation`.  Mechanical enforcement is in
`tests/architecture/test_harness_separation.py`.

## DEV HARNESS — the coding tools that help build SagaSmith

These files and directories belong to Claude Code, Kilo, GSD, and the
mattpocock skills system.  SagaSmith runtime code must never read them.

```
.claude/            Claude Code settings and permissions
.kilo/              Kilo agents, commands, plans, hooks, and GSD workflow library
.kilocode/          Kilo skills mirror (same content as .agents/skills/)
.agents/            Generic dev skills (mattpocock / GSD)
.planning/          GSD planning artifacts: project context, requirements, roadmap,
                    phase plans, and research
AGENTS.md           Coding-assistant brief (Claude Code / Kilo read this)
CONTEXT.md          Harness routing stub (probed by tools at repo root)
CONTEXT-MAP.md      Boundary index (this file + AGENTS.md is the authoritative rule)
LAYOUT.md           This file
kilo.json           Kilo permissions config
skills-lock.json    Pinned mattpocock skills hashes
```

## SAGASMITH RUNTIME — the agentic product itself

These files and directories are SagaSmith.  The coding harness may inspect
them to do implementation work but must not treat them as harness truth.

```
src/sagasmith/      LangGraph agents, deterministic services, providers, TUI, CLI
tests/              Runtime tests
docs/sagasmith/     Product/runtime specs, ADRs, and agent capability catalogs
schemas/            Runtime JSON schemas
pyproject.toml      Package definition
```

## The rule in one sentence

Files on the left must never import, open, or reference files on the right;
files on the right must never import, open, or reference files on the left.
