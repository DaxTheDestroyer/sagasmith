"""Tests for provider logging and retry ladder."""

from __future__ import annotations

from typing import Any

import pytest

from sagasmith.providers import DeterministicFakeClient, invoke_with_retry
from sagasmith.providers.logging import build_provider_log_record
from sagasmith.schemas import LLMRequest, Message
from sagasmith.services.errors import ProviderCallError


def test_build_record_strips_snippet_when_secret_shaped() -> None:
    record = build_provider_log_record(
        provider="fake",
        model="m",
        agent_name="a",
        turn_id=None,
        request_id="r1",
        provider_response_id=None,
        failure_kind="none",
        retry_count=0,
        usage=None,
        cost_estimate_usd=None,
        latency_ms=10,
        response_text="Authorization: Bearer abcdefghijklmnop",
    )
    assert record.safe_snippet is None
    assert record.response_hash != "empty"


def test_build_record_keeps_short_safe_snippet() -> None:
    record = build_provider_log_record(
        provider="fake",
        model="m",
        agent_name="a",
        turn_id=None,
        request_id="r1",
        provider_response_id=None,
        failure_kind="none",
        retry_count=0,
        usage=None,
        cost_estimate_usd=None,
        latency_ms=10,
        response_text="The player opened the door.",
    )
    assert record.safe_snippet == "The player opened the door."


def test_build_record_empty_response_uses_empty_hash() -> None:
    record = build_provider_log_record(
        provider="fake",
        model="m",
        agent_name="a",
        turn_id=None,
        request_id="r1",
        provider_response_id=None,
        failure_kind="none",
        retry_count=0,
        usage=None,
        cost_estimate_usd=None,
        latency_ms=10,
        response_text="",
    )
    assert record.response_hash == "empty"


def test_invoke_with_retry_returns_on_first_success() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    client = DeterministicFakeClient(
        {"default": make_fake_llm_response(text="hello", parsed_json={"ok": True})}
    )
    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[Message(role="user", content="hi")],
        response_format="json_schema",
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[Any] = []
    response = invoke_with_retry(
        client,
        request,
        cheap_model="cheap",
        agent_name="a",
        turn_id=None,
        logger=logs.append,
    )
    assert response.text == "hello"
    assert len(logs) == 1
    assert logs[0].retry_count == 0
    assert logs[0].failure_kind == "none"


def test_invoke_with_retry_logs_client_provider() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    class _OpenRouterLikeClient:
        provider = "openrouter"

        def complete(self, request: LLMRequest) -> Any:
            return make_fake_llm_response(text="hello", parsed_json={"ok": True})

        def stream(self, request: LLMRequest) -> Any:
            return iter([])

    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[Message(role="user", content="hi")],
        response_format="json_schema",
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[Any] = []
    invoke_with_retry(
        _OpenRouterLikeClient(),  # type: ignore[arg-type]
        request,
        cheap_model="cheap",
        agent_name="a",
        turn_id=None,
        logger=logs.append,
    )
    assert logs[0].provider == "openrouter"


@pytest.mark.smoke
def test_invoke_with_retry_exhausts_json_schema_ladder() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    client = DeterministicFakeClient(
        {"default": make_fake_llm_response(text="bad", parsed_json={"ok": "not_bool"})}
    )
    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[Message(role="user", content="hi")],
        response_format="json_schema",
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[Any] = []
    with pytest.raises(ProviderCallError) as exc_info:
        invoke_with_retry(
            client,
            request,
            cheap_model="cheap",
            agent_name="a",
            turn_id=None,
            logger=logs.append,
        )
    msg = str(exc_info.value)
    assert "schema_validation" in msg
    assert "exhausted" in msg
    assert "sk-" not in msg
    assert "Bearer" not in msg
    assert len(logs) == 4
    assert logs[0].retry_count == 0
    assert logs[1].retry_count == 1
    assert logs[2].retry_count == 2
    assert logs[3].retry_count == 3
    assert logs[3].failure_kind == "schema_validation"


def test_invoke_with_retry_retries_provider_schema_validation_errors() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    class _SchemaValidationError(Exception):
        failure_kind = "schema_validation"

    class _RepairingClient:
        provider = "openrouter"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: LLMRequest) -> Any:
            self.calls += 1
            if self.calls < 3:
                raise _SchemaValidationError("provider returned malformed JSON")
            return make_fake_llm_response(text='{"ok":true}', parsed_json={"ok": True})

        def stream(self, request: LLMRequest) -> Any:
            return iter([])

    client = _RepairingClient()
    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[Message(role="user", content="hi")],
        response_format="json_schema",
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[Any] = []
    response = invoke_with_retry(
        client,  # type: ignore[arg-type]
        request,
        cheap_model="cheap",
        agent_name="a",
        turn_id=None,
        logger=logs.append,
    )
    assert response.parsed_json == {"ok": True}
    assert client.calls == 3
    assert [log.failure_kind for log in logs] == [
        "schema_validation",
        "schema_validation",
        "none",
    ]


def test_invoke_with_retry_network_timeout_single_retry() -> None:
    class _FakeTransportError(Exception):
        failure_kind = "network_timeout"

    class _FailingClient:
        def complete(self, request: LLMRequest) -> Any:
            raise _FakeTransportError("timeout")

        def stream(self, request: LLMRequest) -> Any:
            return iter([])

    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[Any] = []
    with pytest.raises(ProviderCallError):
        invoke_with_retry(
            _FailingClient(),  # type: ignore[arg-type]
            request,
            cheap_model="cheap",
            agent_name="a",
            turn_id=None,
            logger=logs.append,
        )
    assert len(logs) == 2
    assert logs[0].failure_kind == "network_timeout"
    assert logs[0].retry_count == 0
    assert logs[1].failure_kind == "network_timeout"
    assert logs[1].retry_count == 1
