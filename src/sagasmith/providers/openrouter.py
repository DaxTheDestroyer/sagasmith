"""OpenRouterClient implementing LLMClient via injected HttpTransport."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sagasmith.evals.redaction import RedactionCanary
from sagasmith.providers.transport import HttpTransport
from sagasmith.schemas.provider import (
    CompletedEvent,
    FailedEvent,
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
    ProviderConfig,
    TokenEvent,
    TokenUsage,
    UsageUpdateEvent,
)
from sagasmith.services.secrets import resolve_secret


@dataclass(frozen=True)
class _OpenRouterError(Exception):
    """Internal transport-layer exception carrying a typed failure_kind."""

    failure_kind: str
    status_code: int

    def __str__(self) -> str:
        return f"OpenRouter error: status={self.status_code} kind={self.failure_kind}"


def _map_status_to_failure_kind(status_code: int) -> str:
    if status_code in (408, 504):
        return "network_timeout"
    if status_code == 429:
        return "rate_limit"
    return "other"


class OpenRouterClient:
    """Real OpenRouter LLMClient implementation."""

    def __init__(
        self,
        config: ProviderConfig,
        transport: HttpTransport,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        if config.provider != "openrouter":
            raise ValueError(
                f"OpenRouterClient requires provider='openrouter', got {config.provider!r}"
            )
        if config.api_key_ref is None:
            raise ValueError("OpenRouterClient requires api_key_ref")
        self._config = config
        self._api_key_ref = config.api_key_ref
        self._transport = transport
        self._base_url = base_url

    def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = resolve_secret(self._api_key_ref)
        try:
            body = self._build_body(request)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "SagaSmith",
            }
            response = self._transport.post_json(
                url=f"{self._base_url}/chat/completions",
                headers=headers,
                json_body=body,
                timeout_seconds=request.timeout_seconds,
            )
            if response.status_code < 200 or response.status_code >= 300:
                kind = _map_status_to_failure_kind(response.status_code)
                raise _OpenRouterError(failure_kind=kind, status_code=response.status_code)

            data = json.loads(response.text)
            choice = data["choices"][0]
            message = choice["message"]
            text = message.get("content", "")
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                provider_cost_usd=data.get("cost"),
            )
            parsed_json: dict[str, Any] | None = None
            if request.response_format == "json_schema":
                try:
                    parsed_json = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise _OpenRouterError(
                        failure_kind="schema_validation", status_code=200
                    ) from exc

            return LLMResponse(
                text=text,
                parsed_json=parsed_json,
                usage=usage,
                provider_response_id=data.get("id"),
                finish_reason=choice.get("finish_reason", "stop"),
            )
        finally:
            del api_key

    def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]:
        api_key = resolve_secret(self._api_key_ref)
        try:
            body = self._build_body(request)
            body["stream"] = True
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "SagaSmith",
            }
            lines = self._transport.post_stream(
                url=f"{self._base_url}/chat/completions",
                headers=headers,
                json_body=body,
                timeout_seconds=request.timeout_seconds,
            )
            accumulated_text = ""
            final_usage: TokenUsage | None = None
            for line in lines:
                if line == "[DONE]":
                    if final_usage is None:
                        final_usage = TokenUsage(
                            prompt_tokens=0, completion_tokens=0, total_tokens=0
                        )
                    yield CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text=accumulated_text,
                            parsed_json=None,
                            usage=final_usage,
                            finish_reason="stop",
                        ),
                    )
                    return
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    accumulated_text += content
                    yield TokenEvent(kind="token", text=content)
                if "usage" in chunk:
                    u = chunk["usage"]
                    final_usage = TokenUsage(
                        prompt_tokens=u.get("prompt_tokens", 0),
                        completion_tokens=u.get("completion_tokens", 0),
                        total_tokens=u.get("total_tokens", 0),
                    )
                    yield UsageUpdateEvent(kind="usage_update", usage=final_usage)
                if "error" in chunk:
                    msg = json.dumps(chunk["error"])[:200]
                    if RedactionCanary().scan(msg):
                        msg = "stream failure (redacted)"
                    yield FailedEvent(kind="failed", failure_kind="other", message=msg)
                    return

            # Stream ended without [DONE] or completed event
            if final_usage is None:
                final_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            yield CompletedEvent(
                kind="completed",
                response=LLMResponse(
                    text=accumulated_text,
                    parsed_json=None,
                    usage=final_usage,
                    finish_reason="stop",
                ),
            )
        except Exception as exc:
            msg = str(exc)[:200]
            if RedactionCanary().scan(msg):
                msg = "stream failure (redacted)"
            yield FailedEvent(kind="failed", failure_kind="network_timeout", message=msg)
            return
        finally:
            del api_key

    def _build_body(self, request: LLMRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.response_format == "json_schema" and request.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{request.agent_name}_schema",
                    "schema": request.json_schema,
                    "strict": True,
                },
            }
        return body
