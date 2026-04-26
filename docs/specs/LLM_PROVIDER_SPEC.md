# SagaSmith - LLM Provider and Cost Specification

**Status:** Draft  
**Audience:** Implementers of provider routing, streaming calls, budget
tracking, retries, and model configuration.  
**Companion specs:** `GAME_SPEC.md`, `STATE_SCHEMA.md`,
`ADR-0001-orchestration-and-skills.md`.

## 1. Purpose

SagaSmith is BYOK: players supply OpenRouter or direct-provider credentials.
This document defines the minimum provider abstraction needed before Oracle
and Orator are implemented.

## 2. Provider Goals

- Model-agnostic runtime with OpenRouter as the preferred first provider.
- Direct-provider support through the same interface.
- Streaming support for Orator.
- Structured JSON support for schema-producing agents.
- Token and cost accounting for CostGovernor.
- Deterministic replay of non-LLM mechanics even when LLM output cannot be
  reproduced exactly.

## 3. Provider Interface

The runtime should expose one `LLMClient` Protocol:

```python
class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...
    def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]: ...
```

`LLMRequest` required fields:

- `agent_name: str`
- `model: str`
- `messages: list[Message]`
- `response_format: "text" | "json_schema"`
- `json_schema: dict | None`
- `temperature: float`
- `max_tokens: int | None`
- `timeout_seconds: int`
- `metadata: dict[str, str]`

`LLMResponse` required fields:

- `text: str`
- `parsed_json: object | None`
- `usage: TokenUsage`
- `provider_response_id: str | None`
- `finish_reason: str`
- `cost_estimate_usd: float | None`

`LLMStreamEvent` variants:

- `token`
- `usage_update`
- `tool_call`
- `completed`
- `failed`

## 4. Model Configuration

Configuration lives in the campaign SQLite DB and may be overridden by env
vars during development.

Minimum settings:

- `provider`: `openrouter` initially; direct providers later.
- `api_key_ref`: keyring or env var reference, never plaintext in campaign
  files.
- `default_model`: model for structured non-streaming agents.
- `narration_model`: model for Orator streaming.
- `cheap_model`: model for classifiers, compression, and safety rewrites.
- `pricing_mode`: `provider_reported` or `static_table`.

## 5. Cost Accounting

CostGovernor consumes `TokenUsage` from every LLM call.

`TokenUsage` required fields:

- `prompt_tokens: int`
- `completion_tokens: int`
- `total_tokens: int`
- `cached_prompt_tokens: int = 0`
- `provider_cost_usd: float | None`

Cost calculation order:

1. Prefer provider-reported cost if present.
2. Else use a static pricing table bundled with the installed package.
3. Else estimate from token counts and mark the cost as approximate.

Budget behavior:

- Warn at 70% and 90% of `session_budget_usd`.
- At 100%, stop before the next paid LLM call.
- The hard stop must produce a local fallback message and checkpoint the turn.

## 6. Streaming Contract

Orator streaming must satisfy:

- First token target: `< 2 s` p50 on a healthy connection.
- Stream events append to the transcript buffer but do not become canonical
  until the turn-close checkpoint succeeds.
- If the stream fails mid-turn, the transcript records a failed generation
  event and the graph retries or falls back according to retry policy.

## 7. Retry Policy

Default retry policy:

- Network timeout: retry once with same model.
- Provider rate limit: retry once after provider-specified delay if doing so
  does not exceed budget.
- JSON schema validation failure: one repair attempt using the same model,
  then one cheap-model repair attempt, then fail the node.
- Safety rewrite failure: SafetyGuard owns the two-rewrite limit specified in
  `GAME_SPEC.md`.

All retries must be logged with:

- `agent_name`
- `provider`
- `model`
- `turn_id`
- `failure_kind`
- `retry_count`

## 8. Secrets

API keys must never be written to:

- player vault
- master vault
- session transcript
- checkpoint payload
- debug logs

Accepted storage options:

- OS keyring, preferred for packaged builds.
- Environment variable reference for development.
- Encrypted local config may be considered later, but is not required for MVP.

## 9. First Vertical Slice

The first implementation only needs:

- OpenRouter client.
- Non-streaming structured JSON call.
- Streaming text call.
- Static fallback pricing table.
- CostGovernor warning/hard-stop behavior.
- Redacted request/response logging.
