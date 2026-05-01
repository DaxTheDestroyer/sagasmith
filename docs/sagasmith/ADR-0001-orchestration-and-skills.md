# ADR-0001: Orchestration Framework and Per-Agent Capability Format

## Status

Accepted — 2026-04-26

## Context

SagaSmith is a multi-agent AI-run TTRPG delivered as a single-player, local-first
Python CLI/TUI application. Per `docs/sagasmith/GAME_SPEC.md` §3, the MVP runtime is
a cooperating set of five agents (Onboarding, Oracle, Rules Lawyer, Orator,
Archivist) plus supporting services (IntentResolver, SafetyGuard, CostGovernor,
DiceService). Each agent has deep, specialized domain competence — PF2e rules,
narrative theory, content-policy reasoning, entity resolution, scene planning —
which collectively exceed what can fit in any single LLM context window.

Two architectural questions must be answered before implementation begins:

1. **Orchestration layer** — how do agents communicate, how does state flow,
   when does each agent run, how are checkpoints and interrupts handled?
2. **Per-agent capability layer** — how does each agent carry its domain
   knowledge without burning its context budget on every turn?

These are orthogonal concerns. This ADR addresses both.

### Hard requirements drawn from `GAME_SPEC.md`

The following are non-negotiable for the MVP and drive the decision:

1. **Model-agnostic / BYOK** (§1.1) — the player supplies OpenRouter or
   direct-provider credentials. Any framework that locks to a single model
   family is disqualified.
2. **Checkpoint after every turn** (§10, §11) — quit/resume must work across
   sessions with zero data loss. Requires first-class persistent state in the
   orchestration layer.
3. **Streaming narration** (§3.3) — first token < 2 s p50. The orchestrator
   must support streaming through its nodes.
4. **Human-in-the-loop mid-turn** (§8, §9) — `/pause`, `/line`, `/retcon`
   interrupt any turn. Requires interrupt primitives in the orchestration layer.
5. **Auditable / deterministic replay** (§3.4) — same seed + same inputs =
   same result. State transitions must be reproducible.
6. **Local-first, `pip install`** (§1.2) — targets non-technical users. Rules
   out JVM/.NET servers and heavy infrastructure.
7. **Progressive-disclosure domain knowledge** — each agent must expose a lean
   discovery surface at context-load time and pull in detailed procedures only
   when a task activates them.

### Candidates evaluated

| Framework | Native Skills? | Checkpoint | Stream | HITL | Model-agnostic | Local-first |
|---|---|---|---|---|---|---|
| LangGraph | No (community pattern + SDK) | Excellent (per-node, SQLite) | Yes | Yes (`interrupt()`) | Yes | Yes |
| CrewAI | Yes (`skills=[]`) | Weak (documented gap) | Partial | Limited | Yes | Yes |
| OpenAI Agents SDK | No | None native | Yes | Yes | No | Yes |
| Claude Agent SDK | Yes (reference impl) | Via SDK | Yes | Yes | No (Claude-only) | Yes |
| PydanticAI | No (community pattern) | Immature | Yes | Partial | Yes | Yes |
| Google ADK | Partial (`SkillToolset`) | Yes | Yes | Yes | No (Gemini-first) | Yes |
| AutoGen / AG2 | No | Via AG2 extensions | Partial | Yes | Yes | Yes |
| Hand-rolled | Build it | Build it | Build it | Build it | Yes | Yes |

Hard requirements 1 (BYOK) and 2 (checkpointing) eliminate every framework that
offers native Agent Skills support. LangGraph, PydanticAI, and hand-rolled
survive the hard filters; among these, LangGraph dominates on streaming,
interrupts, checkpointing maturity, and auditable replay.

### The portability insight

Agent Skills is an **architectural pattern**, not a framework feature. The
specification (<https://agentskills.io/specification>) defines a filesystem
format (`SKILL.md` with YAML frontmatter + markdown body, plus optional
`scripts/`, `references/`, `assets/`) and a progressive-disclosure loading
model (metadata → instructions → resources). Every candidate framework can
implement this pattern. Confirmed by:

- Anthropic's Claude Agent SDK (native, reference implementation).
- CrewAI's `Agent(skills=[...])` parameter (shipped 2025–2026).
- The published LangGraph integration pattern (Pessini, Feb 2026:
  *"Stop Stuffing Your System Prompt: Build Scalable Agent Skills in
  LangGraph"*) with reference repo.
- The `phronetic-ai/agent-skills-sdk` project, a pip-installable SDK providing
  Agent Skills adapters for LangChain, CrewAI, and custom frameworks.
- A PydanticAI community implementation (Cole Medin, Jan 2026).

**This means the skill catalog is portable across orchestration choices.** If
the framework decision ever needs to change, the skill packages survive.

## Decision

SagaSmith adopts **LangGraph** as the orchestration framework and
**Agent Skills** (per the agentskills.io specification) as the per-node
capability format.

### Composition model

- **LangGraph operates at the orchestration layer.** Each MVP agent
  (Onboarding, Oracle, Rules Lawyer, Orator, Archivist) is a LangGraph node.
  A typed `StateGraph` carries `PlayerProfile`, `SceneBrief`, `MemoryPacket`,
  `StateDelta`, `CombatState`, and related payloads between nodes. Conditional
  edges route turns by pillar (combat / exploration / social / puzzle).
- **Agent Skills operate at the per-node capability layer.** Each node owns a
  `skills/` directory containing one subdirectory per skill, each with a
  `SKILL.md` and optional `scripts/`, `references/`, `assets/`. The node's
  LLM call receives a skill catalog (`name` + `description` per skill, ~100
  tokens each) in its system prompt and uses a `load_skill(name)` tool to
  activate skills as the turn requires.
- **Cross-cutting skills** (e.g., `schema-validation`, `safety-redline-check`)
  live in a shared `skills/` root at the package level and are registered
  with multiple nodes by their construction-time skill lists.
- **Checkpointing** uses LangGraph's `SqliteSaver` backed by the same SQLite
  database that stores session transcripts, roll logs, and callbacks. One
  checkpoint per turn.
- **Persistence** of canon (vault pages, embeddings) lives below the
  orchestration layer: Archivist's node writes to SQLite, LanceDB, and the
  Obsidian-compatible vault. LangGraph state carries references, not bulk
  content.

### Directory layout (binding)

```
sagasmith/
├── graph/
│   ├── state.py              # Typed LangGraph state (TypedDict / Pydantic)
│   ├── graph.py              # StateGraph construction
│   └── routing.py            # Conditional-edge logic
├── agents/
│   ├── onboarding/
│   │   ├── node.py
│   │   ├── prompts.py
│   │   └── skills/           # Per-agent SKILL.md directories
│   ├── oracle/
│   │   ├── node.py
│   │   └── skills/
│   ├── rules_lawyer/
│   │   ├── node.py
│   │   └── skills/
│   ├── archivist/
│   │   ├── node.py
│   │   └── skills/
│   └── orator/
│       ├── node.py
│       └── skills/
├── skills/                   # Cross-cutting skills shared by multiple agents
└── services/                 # DiceService, SafetyGuard, CostGovernor, IntentResolver
```

### Skill adapter

The LangGraph ↔ Agent Skills glue is a small module (estimated 150–300 LOC)
providing:

- A `SkillStore` that scans skill directories at startup, parses frontmatter,
  and exposes discovery metadata.
- A `load_skill` tool bound to each agent node, which fetches the full
  `SKILL.md` body and returns it as a tool response.
- A catalog-injection helper that renders the available skill list into each
  node's system prompt at call time.

We will prototype this ourselves rather than adopting `agent-skills-sdk`
upfront. Rationale: the surface is small, keeping it first-party avoids a
dependency we do not yet understand the trade-offs of, and the adapter is a
natural vehicle for SagaSmith-specific extensions (e.g., binding skill-bundled
scripts to LangGraph tools, enforcing `ContentPolicy` at activation time). We
will re-evaluate adopting `agent-skills-sdk` if the in-house adapter exceeds
~500 LOC or if skill-sharing interop with other products becomes a priority.

## Consequences

### Positive

- **Hard requirements met.** Checkpointing, streaming, HITL interrupts,
  deterministic replay, model-agnosticism, and local-first distribution all
  come for free from LangGraph.
- **Context budget controlled.** Each agent's per-turn context load is
  bounded by its base prompt plus the skill catalog (~500–1000 tokens) plus
  the specific skills it activates for the turn (typically 1–3 skills,
  2–5k tokens total). This is ~10–20× smaller than stuffing full domain
  knowledge into every system prompt.
- **Skills are portable assets.** If LangGraph is ever replaced, the skill
  directories move unchanged to the new orchestrator; only the adapter is
  rewritten.
- **Deferred agents have a clean migration path.** ArtistAgent, Cartographer,
  Puppeteer, and Villain (per `docs/WISHLIST.md`) begin life as skills inside
  Oracle (e.g., `oracle/skills/inline-npc-creation/`). When they graduate to
  standalone agents, the skill directory moves to
  `agents/<new_agent>/skills/` and a new LangGraph node wraps it. No breaking
  change to the skill's interface.
- **Audit and eval alignment.** LangGraph checkpoints + per-skill activation
  logs give us a turn-by-turn trace of which agent ran, which skills
  activated, what state changed, and what prose was generated. This is the
  substrate the eval harness will consume.
- **Per-skill eval fixtures.** Each skill becomes an independent regression
  target (e.g., `oracle/skills/encounter-budget/` ships with fixtures that
  validate against PF2e XP tables). Granular, testable capability boundaries.

### Negative / trade-offs

- **LangGraph learning curve.** The graph mental model and typed-state
  discipline are more demanding than CrewAI's role-first abstraction.
  Mitigated by SagaSmith's natural fit to the graph model (agents as nodes,
  scenes as state, conditional routing by pillar).
- **Skill adapter must be built.** 150–300 LOC of glue to implement the
  Agent Skills pattern. Not free, but small, well-scoped, and backed by a
  documented community reference implementation.
- **Activation round-trips cost latency.** A skill activation is a tool-call
  round-trip: the LLM decides to load → we inject the skill → the LLM
  re-reasons. For trivial turns this is overhead. Mitigated by keeping
  always-relevant skills inlined in a node's base prompt (e.g., Orator's
  core rendering skill) and reserving activation for turn-specific procedures.
- **Framework choice risk on Skills native support.** If CrewAI or another
  framework resolves its checkpointing story, the "native skills" argument
  could reopen. The portability of the skill catalog means this is a
  recoverable risk, not a lock-in.
- **Not every agent benefits equally.** Rules Lawyer is a large winner
  (vast domain, turn-relevant slices are tiny). Oracle and Archivist are
  strong winners. Orator's skills are fewer and mostly stylistic. Onboarding
  is bounded by a fixed nine-phase flow, so skills there are more about
  structured procedure than context control. Skill granularity will be
  tuned per agent during the skills-speccing pass.

## Alternatives considered

### CrewAI (rejected)

Offers native `Agent(skills=[...])` support, matching the Agent Skills
specification. Its role-first model (`role`, `goal`, `backstory`) maps
cleanly onto SagaSmith's agent concept. However, CrewAI's checkpointing is
documented as weak in both official material and in
`.kilo/get-shit-done/references/ai-frameworks.md` (listed as a weakness:
*"Limited checkpointing, coarse error handling"* and as an explicit
anti-pattern: *"Using CrewAI for complex stateful workflows — Checkpointing
gaps will bite you in production"*). Since per-turn checkpointing is a hard
requirement (`GAME_SPEC.md` §10, §11), this is disqualifying. Skills-native
support is the wrong axis to optimize when it forces a trade on a harder
requirement.

### Claude Agent SDK (rejected)

The reference implementation of Agent Skills — natively supports
filesystem-based skill discovery, `skills=[...]` parameter, automatic
progressive disclosure. If SagaSmith were Claude-only, this would be the
clear choice. However, the BYOK requirement (`GAME_SPEC.md` §1.1) means the
player may bring OpenAI, Google, Mistral, local, or OpenRouter-routed
credentials. Claude-only lock-in is disqualifying.

### OpenAI Agents SDK (rejected)

Simple mental model and growing Skills ecosystem via the `Skill` tool
convention. Rejected for the same reasons as Claude Agent SDK (BYOK) plus
lack of native persistent state. The combination of OpenAI vendor lock-in
and missing checkpointing makes this a double disqualification.

### PydanticAI (viable secondary, not selected)

Clean Pydantic-native type system that aligns well with our JSON-Schema-first
state design. A well-documented community implementation of the Agent Skills
pattern exists (Cole Medin, Jan 2026). Not selected because:

- Checkpointing/persistent state is less mature than LangGraph's `SqliteSaver`.
- Human-in-the-loop interrupt semantics are partial, not first-class.
- Graph-style branching (combat vs. social vs. exploration) is less
  prescribed, meaning more scaffolding work for us.
- Smaller community → fewer pre-solved edge cases.

Viable fallback if LangGraph proves to have friction we don't currently
anticipate. The skill catalog transfers without modification.

### Google ADK (rejected)

Mentions of a `SkillToolset` suggest emerging native support. Rejected for
the same BYOK reason as Claude Agent SDK — in practice ADK is Gemini-first
and ecosystem integrations (Vertex AI, Google Search, BigQuery) lean heavily
on Google Cloud. Conflicts with local-first + model-agnostic requirements.

### AutoGen / AG2 / Microsoft Agent Framework (rejected)

Ecosystem is fragmented (AutoGen in maintenance mode, AG2 fork active,
Microsoft Agent Framework in preview). `.kilo/get-shit-done/references/ai-frameworks.md`
flags this as a *"genuine long-term risk."* Not worth taking in a
greenfield project.

### Hand-rolled orchestrator (rejected)

A thin Python coordinator calling agent functions in a loop is feasible for
the simplest cases, but implementing checkpointing, time-travel debugging,
streaming modes, interrupt semantics, and typed-state reduction from scratch
is months of undifferentiated work. The moment the coordinator grows beyond
~500 LOC, it is LangGraph, poorly. Rejected.

## Implementation notes

- The **skill catalog** (what skills exist per agent, with their descriptions
  and success signals) is captured as one file per agent under
  `docs/sagasmith/agents/` before implementation. `docs/sagasmith/agents/README.md`
  defines the catalog template and file list.
- The actual `SKILL.md` files ship in the codebase under the directory
  layout defined above. They are the implementation artifact.
- Each skill's success signal translates into at least one eval fixture.
- The skill adapter will be implemented as part of the graph bootstrap work
  in the first implementation milestone.

## References

- `docs/sagasmith/GAME_SPEC.md` §1.1, §1.2, §1.3, §3, §4, §8, §9, §10, §11
- `docs/WISHLIST.md` — cross-references for deferred-agent migration path
- Agent Skills specification: <https://agentskills.io/specification>
- `.kilo/get-shit-done/references/ai-frameworks.md` — framework comparison
  matrix used in the evaluation
- Pessini, L. (2026-02-16). *Stop Stuffing Your System Prompt: Build
  Scalable Agent Skills in LangGraph.* Medium.
  <https://medium.com/@pessini/stop-stuffing-your-system-prompt-build-scalable-agent-skills-in-langgraph-a9856378e8f6>
- Reference implementation repo: <https://github.com/pessini/langgraph-skills-agent>
- Agent Skills SDK (fallback option): <https://github.com/phronetic-ai/agentskills>
- LangGraph: <https://langchain-ai.github.io/langgraph/>
- CrewAI Skills documentation: <https://docs.crewai.com/en/concepts/skills>
- Claude Agent SDK Skills documentation:
  <https://docs.claude.com/en/docs/agent-sdk/skills>
