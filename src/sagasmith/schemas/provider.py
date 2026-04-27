"""Provider request/response/config schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from sagasmith.schemas.common import SchemaModel
from sagasmith.services.secrets import SecretRef


class Message(SchemaModel):
    """Single message in an LLM request."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str


class LLMRequest(SchemaModel):
    """Structured request to an LLM provider."""

    agent_name: str
    model: str
    messages: list[Message]
    response_format: Literal["text", "json_schema"]
    json_schema: dict[str, Any] | None = None
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: int = Field(gt=0, le=600)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_response_format(self) -> LLMRequest:
        if self.response_format == "json_schema" and self.json_schema is None:
            raise ValueError("json_schema is required when response_format is json_schema")
        if self.response_format == "text" and self.json_schema is not None:
            raise ValueError("json_schema must be None when response_format is text")
        return self


class TokenUsage(SchemaModel):
    """Token usage returned by a provider."""

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_prompt_tokens: int = Field(ge=0, default=0)
    provider_cost_usd: float | None = Field(default=None, ge=0)


class LLMResponse(SchemaModel):
    """Structured response from an LLM provider."""

    text: str
    parsed_json: dict[str, Any] | list[Any] | None = None
    usage: TokenUsage
    provider_response_id: str | None = None
    finish_reason: str
    cost_estimate_usd: float | None = Field(default=None, ge=0)


class TokenEvent(SchemaModel):
    """Stream event: a token of text."""

    kind: Literal["token"]
    text: str


class UsageUpdateEvent(SchemaModel):
    """Stream event: usage update."""

    kind: Literal["usage_update"]
    usage: TokenUsage


class ToolCallEvent(SchemaModel):
    """Stream event: tool call."""

    kind: Literal["tool_call"]
    name: str
    arguments_json: str


class CompletedEvent(SchemaModel):
    """Stream event: completion finished."""

    kind: Literal["completed"]
    response: LLMResponse


class FailedEvent(SchemaModel):
    """Stream event: completion failed."""

    kind: Literal["failed"]
    failure_kind: Literal["network_timeout", "rate_limit", "schema_validation", "other"]
    message: str


LLMStreamEvent = TokenEvent | UsageUpdateEvent | ToolCallEvent | CompletedEvent | FailedEvent


class ProviderConfig(SchemaModel):
    """Campaign-level provider configuration."""

    provider: Literal["openrouter", "fake"]
    api_key_ref: SecretRef | None = None
    default_model: str
    narration_model: str
    cheap_model: str
    pricing_mode: Literal["provider_reported", "static_table"]

    @model_validator(mode="after")
    def _validate_provider_key(self) -> ProviderConfig:
        if self.provider == "openrouter" and self.api_key_ref is None:
            raise ValueError("api_key_ref is required when provider is openrouter")
        if self.provider == "fake" and self.api_key_ref is not None:
            raise ValueError("api_key_ref must be None when provider is fake")
        return self


class ProviderLogRecord(SchemaModel):
    """Metadata-only provider log record."""

    provider: Literal["openrouter", "fake"]
    model: str
    agent_name: str
    turn_id: str | None = None
    request_id: str
    provider_response_id: str | None = None
    failure_kind: Literal["none", "network_timeout", "rate_limit", "schema_validation", "other"]
    retry_count: int = Field(ge=0)
    usage: TokenUsage | None = None
    cost_estimate_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    safe_snippet: str | None = None
    response_hash: str
    timestamp: str
