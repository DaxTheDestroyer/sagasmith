# Changelog

All notable changes to the AI-TTRPG project (SagaSmith) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project will adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once released.

## [Unreleased]

### Planning Direction - 2026-04-23

#### Changed
- **Development Workflow Simplified**
  - Removed `docs/specs/HARNESS_SPEC.md`.
  - Replaced the custom hybrid harness direction with the decision to use upstream GSD directly in Kilo.
  - Project-specific process work will focus on SagaSmith specs, milestones, ADRs, tests, evals, and CI rather than porting or maintaining harness assets.
  - Rationale: GSD already supports Kilo, so recreating a Superpowers/GSD/Paul hybrid harness would add maintenance cost before the game runtime exists.

### Planning Phase - 2026-04-22

#### Changed
- **Project Naming Convention Finalized**
  - GitHub repository name: `sagasmith`
  - PyProject package name: `ai-sagasmith`
  - Python source package: `sagasmith`
  - Naming conventions retained as planning decisions for future project scaffolding
  - Previous working name was `AI-TTRPG-GoAnywhereDoAnything`

- **Agent Naming: Architect → Oracle**
  - Renamed `ArchitectAgent` to `OracleAgent` throughout specifications
  - The Oracle agent serves as the GM (world-building, campaign seeding, scene planning, callback tracking, encounter design)
  - Updated all references in `docs/specs/GAME_SPEC.md`:
    - Section 3.2: Agent definition and responsibilities
    - Section 3.7: Deferred agents interactions
    - Section 5.1: Character creation flow
    - Section 5.5: Encounter design
    - Section 9: Safety and content controls
  - Rationale: Better reflects the agent's role as the omniscient game master who reveals the world and its possibilities

#### Notes
- All changes made during planning phase, before repository creation
- Specifications updated to reflect final naming decisions
- Oracle agent now appears alongside Orator agent (O-O adjacency accepted)
