---
description: Ingest external plans with conflict detection against project decisions before writing anything.
argument-hint: "--from <filepath>"
tools:
  read: true
  write: true
  edit: true
  bash: true
  glob: true
  grep: true
  question: true
  task: true
---

<objective>
Import external plan files into the GSD planning system with conflict detection against PROJECT.md decisions.

- **--from**: Import an external plan file, detect conflicts, write as GSD PLAN.md, validate via gsd-plan-checker.

Future: `--prd` mode for PRD extraction is planned for a follow-up PR.
</objective>

<execution_context>
@C:/PersonalDevFiles/KiloCodeFiles/AI-TTRPG-GoAnywhereDoAnything/.kilo/get-shit-done/workflows/import.md
@C:/PersonalDevFiles/KiloCodeFiles/AI-TTRPG-GoAnywhereDoAnything/.kilo/get-shit-done/references/ui-brand.md
@C:/PersonalDevFiles/KiloCodeFiles/AI-TTRPG-GoAnywhereDoAnything/.kilo/get-shit-done/references/gate-prompts.md
@C:/PersonalDevFiles/KiloCodeFiles/AI-TTRPG-GoAnywhereDoAnything/.kilo/get-shit-done/references/doc-conflict-engine.md
</execution_context>

<context>
$ARGUMENTS
</context>

<process>
Execute the import workflow end-to-end.
</process>
