# ORC License Notice — SagaSmith

This file governs the **tabletop game rules content** bundled with SagaSmith.
It does **not** govern SagaSmith's source code, which is licensed separately
under the Apache License, Version 2.0 (see [LICENSE](LICENSE)).

---

## 1. Licensed under the ORC License

The Pathfinder 2e Remaster game mechanics expressed in this project — stat
blocks, condition definitions, degree-of-success tables, action economies,
skill DCs, monster data, and any other rules expression incorporated from
Paizo's Remaster releases — are made available under the **ORC License
v1.0**, administered by Azora Law, Ltd.

The full text of the ORC License v1.0 must accompany any redistribution of
this content. The canonical text is published by Azora Law and is included
in this repository as `ORC-LICENSE-v1.0.txt`.

> **Maintainer note.** Before the first public release, download the
> canonical ORC License v1.0 text from Azora Law and commit it to the
> repository root as `ORC-LICENSE-v1.0.txt`. Do not paraphrase or hand-type
> the license text — use the official document.

---

## 2. Licensed Material Notice

The following Licensed Material is incorporated into SagaSmith under the
ORC License:

- **Pathfinder Second Edition Remaster** — game mechanics, stat blocks,
  conditions, action economy, degree-of-success math, skill DC tables,
  monster statistics, and equipment data, as published by Paizo Inc. under
  the ORC License.

  Specific files in this repository that incorporate Licensed Material
  include (non-exhaustive):

  - `docs/sagasmith/PF2E_MVP_SUBSET.md`
  - `src/sagasmith/rules/` (rules engine and data tables)
  - any bundled monster, spell, condition, or equipment data files
  - any test fixtures that encode PF2e rules outcomes

If you fork or reuse these files, you must comply with the ORC License,
including reproducing this Licensed Material notice.

---

## 3. Reserved Material Notice

The following material is **Reserved** and is **not** licensed under the
ORC License. It may not be used, reproduced, or distributed under ORC terms:

- The name **"SagaSmith"** and any associated logos, marks, or branding.
- The SagaSmith product narrative voice, prompt text, agent personalities
  (Oracle, RulesLawyer, Orator, Archivist), and the specific Agent Skills
  modules authored for this project.
- All original prose, scenarios, NPCs, locations, plot beats, and campaign
  content authored by SagaSmith contributors and stored in vaults,
  fixtures, or evals.
- Source code, schemas, build tooling, tests, and documentation authored
  by SagaSmith contributors. (These are licensed under Apache 2.0; see
  [LICENSE](LICENSE).)
- Third-party trademarks and Product Identity, including but not limited
  to Paizo Inc.'s **iconic character names** (e.g., Valeros, Merisiel,
  Ezren, Kyra, Seoni, Harsk, Lem, Lini, Sajan, Amiri, Feiya), Paizo
  trademarks, logos, and any Paizo content that is **not** released under
  the ORC License.

> **Maintainer note.** SagaSmith currently references the iconic name
> "Valeros" in `src/sagasmith/rules/first_slice.py`. That name is Paizo
> Product Identity, not ORC-licensed content. Replace it with a generic
> level-1 fighter pregen before public release, or remove it from any
> redistributed bundle.

---

## 4. Attribution

SagaSmith is an independent product produced by the SagaSmith contributors.
It is **not** published, endorsed, or specifically approved by Paizo Inc.
References to Pathfinder Second Edition rules are used under the ORC
License v1.0. Pathfinder is a registered trademark of Paizo Inc.

---

## 5. Compatibility

The Apache 2.0 license on SagaSmith's source code and the ORC License on
SagaSmith's bundled rules content cover **disjoint material**. Apache 2.0
does not relicense ORC content, and ORC does not relicense Apache code.
Downstream redistributors must comply with both licenses for the portions
of the work each one covers.
