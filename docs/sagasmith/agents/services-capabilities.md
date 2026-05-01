# Shared Services Capabilities Catalog

**Status:** Draft  
**Audience:** Implementers of deterministic services and shared capabilities
consumed by multiple agents.  
**Companion specs:** `GAME_SPEC.md` §3.6, `STATE_SCHEMA.md`,
`LLM_PROVIDER_SPEC.md`, `PERSISTENCE_SPEC.md`.

## 1. Scope Context

Services are not first-class GM agents. They provide deterministic or bounded
hybrid capabilities to the graph and agents: intent resolution, safety checks,
cost tracking, dice, validation, and file-write primitives.

## 2. Capabilities

### 2.1 `intent-resolution`

**Purpose:** Translate raw player input into candidate mechanical or narrative
intents.

**Inputs -> Outputs:** `(player_input, scene_context, character_sheet)` ->
intent candidates and confidence scores.

**Implementation surface:** `hybrid`.

**Key dependencies:** RulesLawyer check proposal models, Oracle scene context.

**Success signal:** Common action phrases map to expected candidate checks
without LLM fallback; ambiguous phrases request clarification or produce
ranked options.

### 2.2 `safety-pre-gate`

**Purpose:** Block or reroute scene intents before generation when they violate
hard limits.

**Inputs -> Outputs:** `(scene_intent, ContentPolicy)` -> allow, fade, reroute,
or block.

**Implementation surface:** `hybrid`.

**Key dependencies:** `ContentPolicy`, Oracle content-policy routing.

**Success signal:** Hard-limit fixture intents never reach Orator.

### 2.3 `safety-post-gate`

**Purpose:** Scan generated prose and request rewrites or fallback text when
content violates policy.

**Inputs -> Outputs:** `(generated_text, ContentPolicy)` -> approved text,
rewrite request, or fallback.

**Implementation surface:** `hybrid`.

**Key dependencies:** Orator output, safety event log.

**Success signal:** A redlined 100-turn regression produces no prohibited
player-facing prose and logs every rewrite/fallback.

### 2.4 `cost-governor`

**Purpose:** Track token/cost usage and enforce warning and hard-stop budget
rules.

**Inputs -> Outputs:** `(LLMResponse.usage, BudgetPolicy, CostState)` ->
updated `CostState` and optional stop event.

**Implementation surface:** `deterministic`.

**Key dependencies:** `LLM_PROVIDER_SPEC.md`, `STATE_SCHEMA.md` `CostState`.

**Success signal:** Warnings fire exactly once at 70% and 90%; hard stop occurs
before a paid call that would exceed budget.

### 2.5 `seeded-dice-service`

**Purpose:** Provide reproducible dice rolls for all mechanics.

**Inputs -> Outputs:** `(dice_expression, seed, roll_context)` -> `RollResult`.

**Implementation surface:** `deterministic`.

**Key dependencies:** `STATE_SCHEMA.md` `RollResult`, roll log table.

**Success signal:** Same seed and roll context reproduce exact natural and
total results.

### 2.6 `schema-validation`

**Purpose:** Validate agent outputs and persisted records against Pydantic/JSON
Schema contracts.

**Inputs -> Outputs:** `(schema_id, payload)` -> valid payload or structured
validation error.

**Implementation surface:** `deterministic`.

**Key dependencies:** `STATE_SCHEMA.md`, `VAULT_SCHEMA.md`.

**Success signal:** Invalid records fail before persistence or downstream
agent consumption.

### 2.7 `safety-redline-check`

**Purpose:** Defense-in-depth scan for redlined content in player-visible
artifacts such as player vault pages and recaps.

**Inputs -> Outputs:** `(artifact_text, ContentPolicy)` -> pass or violation
report.

**Implementation surface:** `hybrid`.

**Key dependencies:** ContentPolicy, Archivist player-vault-sync.

**Success signal:** Fixture player vault sync blocks or repairs pages
containing redlined content before projection.

### 2.8 `atomic-file-write`

**Purpose:** Write files so partial content never becomes canonical.

**Inputs -> Outputs:** `(target_path, content, validator)` -> write report.

**Implementation surface:** `deterministic`.

**Key dependencies:** `PERSISTENCE_SPEC.md`, vault page validators.

**Success signal:** Induced crash during write leaves either the old valid file
or the new valid file, never a partial file.

### 2.9 `command-dispatch`

**Purpose:** Parse slash commands and route them to graph interrupts or service
handlers.

**Inputs -> Outputs:** `(raw_input, SagaState)` -> command event or normal
player action.

**Implementation surface:** `deterministic`.

**Key dependencies:** TUI input line, LangGraph interrupt handling.

**Success signal:** `/pause`, `/line`, `/retcon`, `/save`, `/sheet`, `/clock`,
and `/budget` dispatch to the expected handlers.

### 2.10 `llm-call-logging`

**Purpose:** Record LLM call metadata, token usage, cost estimates, and failure
events without leaking secrets.

**Inputs -> Outputs:** `(LLMRequest, LLMResponse | error)` -> redacted log row.

**Implementation surface:** `deterministic`.

**Key dependencies:** `LLM_PROVIDER_SPEC.md`, SQLite logs, secret redaction.

**Success signal:** API keys and auth headers never appear in logs; token/cost
records reconcile with CostGovernor.

## 3. First-Slice Required Capabilities

The first vertical slice requires:

- `intent-resolution`
- `cost-governor`
- `seeded-dice-service`
- `schema-validation`
- `atomic-file-write`
- `command-dispatch`
- `llm-call-logging`

Safety post-gate can initially run as a simple rule-backed classifier, but the
service boundary should exist from the first TUI loop.
