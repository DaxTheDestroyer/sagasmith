"""Tests for OpenRouterClient."""

from __future__ import annotations

import json
import os

import pytest

from sagasmith.providers.openrouter import OpenRouterClient, _OpenRouterError
from sagasmith.providers.transport import HttpResponse
from sagasmith.schemas.provider import (
    LLMRequest,
    LLMResponse,
    ProviderConfig,
)
from sagasmith.services.secrets import SecretRef


def _make_config() -> ProviderConfig:
    return ProviderConfig(
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="SAGASMITH_TEST_OPENROUTER_KEY"),
        default_model="openai/gpt-4o-mini",
        narration_model="openai/gpt-4o-mini",
        cheap_model="openai/gpt-4o-mini",
        pricing_mode="provider_reported",
    )


def test_openrouter_rejects_non_openrouter_config() -> None:
    fake_config = ProviderConfig(
        provider="fake",
        api_key_ref=None,
        default_model="m",
        narration_model="m",
        cheap_model="m",
        pricing_mode="static_table",
    )
    with pytest.raises(ValueError, match="openrouter"):
        OpenRouterClient(fake_config, transport=None)  # type: ignore[arg-type]


def test_openrouter_complete_text_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=200,
        text=json.dumps(
            {
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "id": "resp-123",
            }
        ),
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    response = client.complete(request)
    assert isinstance(response, LLMResponse)
    assert response.text == "hello"
    assert response.usage.prompt_tokens == 10
    assert response.parsed_json is None


def test_openrouter_complete_json_schema_parses_parsed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=200,
        text=json.dumps(
            {
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
            }
        ),
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="json_schema",
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        temperature=0.0,
        timeout_seconds=10,
    )
    response = client.complete(request)
    assert response.parsed_json == {"ok": True}


def test_openrouter_complete_json_schema_parse_failure_raises_schema_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=200,
        text=json.dumps(
            {
                "choices": [{"message": {"content": "not-json"}, "finish_reason": "stop"}],
                "usage": {},
            }
        ),
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="json_schema",
        json_schema={"type": "object"},
        temperature=0.0,
        timeout_seconds=10,
    )
    with pytest.raises(_OpenRouterError) as exc_info:
        client.complete(request)
    assert exc_info.value.failure_kind == "schema_validation"


def test_openrouter_complete_429_maps_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=429,
        text="Rate limited",
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    with pytest.raises(_OpenRouterError) as exc_info:
        client.complete(request)
    assert exc_info.value.failure_kind == "rate_limit"


@pytest.mark.smoke
def test_openrouter_complete_error_message_does_not_contain_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.providers.conftest import FakeHttpTransport

    leak_marker = "sk-or-v1-LEAKMARKERABCDEFG"
    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", leak_marker)

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=500,
        text=leak_marker,
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    with pytest.raises(_OpenRouterError) as exc_info:
        client.complete(request)
    msg = str(exc_info.value)
    assert leak_marker not in msg
    assert "sk-" not in msg


def test_openrouter_stream_yields_tokens_then_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_stream_lines["https://openrouter.ai/api/v1/chat/completions"] = [
        json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
        json.dumps({"choices": [{"delta": {"content": " world"}}]}),
        "[DONE]",
    ]

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    events = list(client.stream(request))
    token_events = [e for e in events if e.kind == "token"]
    completed_events = [e for e in events if e.kind == "completed"]
    assert len(token_events) == 2
    assert len(completed_events) == 1
    assert completed_events[0].response.text == "Hello world"


@pytest.mark.smoke
def test_openrouter_stream_failure_message_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.providers.conftest import FakeHttpTransport

    leak_marker = "sk-or-v1-LEAKMARKERABCDEFG"
    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", leak_marker)

    transport = FakeHttpTransport()
    transport.scripted_stream_lines["https://openrouter.ai/api/v1/chat/completions"] = [
        json.dumps({"error": {"message": leak_marker}}),
    ]

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    events = list(client.stream(request))
    failed = [e for e in events if e.kind == "failed"]
    assert len(failed) == 1
    assert failed[0].message == "stream failure (redacted)"


def test_openrouter_complete_does_not_log_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.providers.conftest import FakeHttpTransport

    monkeypatch.setenv("SAGASMITH_TEST_OPENROUTER_KEY", "sk-or-v1-test")

    transport = FakeHttpTransport()
    transport.scripted_json["https://openrouter.ai/api/v1/chat/completions"] = HttpResponse(
        status_code=200,
        text=json.dumps(
            {
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {},
            }
        ),
        headers={},
    )

    client = OpenRouterClient(_make_config(), transport)
    request = LLMRequest(
        agent_name="a",
        model="openai/gpt-4o-mini",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    response = client.complete(request)
    # API key must not leak into the response text or parsed_json
    assert "sk-or-v1-" not in response.text


@pytest.mark.skipif(
    os.environ.get("SAGASMITH_RUN_LIVE_OPENROUTER") != "1",
    reason="live OpenRouter verification opt-in only (D-01)",
)
def test_live_openrouter_cheap_completion() -> None:
    from sagasmith.providers.transport import HttpxTransport

    api_key = os.environ.get("SAGASMITH_TEST_OPENROUTER_KEY", "")
    assert api_key, "SAGASMITH_TEST_OPENROUTER_KEY must be set for live verification"

    config = ProviderConfig(
        provider="openrouter",
        api_key_ref=SecretRef(kind="env", name="SAGASMITH_TEST_OPENROUTER_KEY"),
        default_model="openai/gpt-4o-mini",
        narration_model="openai/gpt-4o-mini",
        cheap_model="openai/gpt-4o-mini",
        pricing_mode="provider_reported",
    )
    with HttpxTransport() as transport:
        client = OpenRouterClient(config, transport)
        request = LLMRequest(
            agent_name="live_test",
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello."}],
            response_format="text",
            temperature=0.0,
            timeout_seconds=30,
        )
        response = client.complete(request)
        assert response.text
        assert response.usage.total_tokens > 0
