# Agent Skills Catalogs

**Status:** Draft  
**Audience:** Implementers of SagaSmith agent nodes and Agent Skills packages.

This folder contains pre-implementation capability catalogs for each agent and
shared service group. The catalogs are not the final `SKILL.md` files. They
define the stable skill names, responsibilities, data contracts, dependencies,
and success signals that later `SKILL.md` packages must implement.

## Planned Catalogs

| File | Status |
|---|---|
| `archivist-skills.md` | Drafted |
| `rules-lawyer-skills.md` | Drafted |
| `oracle-skills.md` | Drafted |
| `orator-skills.md` | Planned |
| `onboarding-skills.md` | Planned |
| `services-capabilities.md` | Drafted |

## Skill Entry Template

Each skill entry uses these fields:

| Field | Purpose |
|---|---|
| **Name** | Stable `kebab-case` name, max 64 chars. Becomes the eventual `SKILL.md` frontmatter `name`. |
| **Purpose** | One sentence describing what the agent can do because of this skill. |
| **Inputs -> Outputs** | Plain-language data contract, citing `STATE_SCHEMA.md` models where applicable. |
| **Implementation surface** | `deterministic`, `prompted`, `hybrid`, or `tool-call`. |
| **Key dependencies** | Other skills, services, schemas, or storage layers required. |
| **Success signal** | One observable result that can seed a fixture or eval. |

Optional `Notes / open questions` sections are allowed when a skill has a
design uncertainty that should stay attached to that skill.

## Conventions

- Deterministic capabilities still get skill entries if they are part of an
  agent's capability surface.
- Shared utilities such as schema validation belong in
  `services-capabilities.md`; agent catalogs reference them by name.
- Catalog changes should accompany any later implementation change that alters
  skill behavior, inputs, outputs, or success criteria.

## References

- `docs/sagasmith/ADR-0001-orchestration-and-skills.md`
- `docs/sagasmith/GAME_SPEC.md`
- `docs/sagasmith/STATE_SCHEMA.md`
