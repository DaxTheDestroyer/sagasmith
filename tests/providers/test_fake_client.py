"""Tests for DeterministicFakeClient."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.providers import DeterministicFakeClient, invoke_with_retry
from sagasmith.providers.fake import __file__ as fake_file
from sagasmith.schemas import LLMRequest, Message


def test_fake_client_complete_returns_scripted_response() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    client = DeterministicFakeClient({"oracle": make_fake_llm_response(text="hello")})
    request = LLMRequest(
        agent_name="oracle",
        model="m",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    response = client.complete(request)
    assert response.text == "hello"


def test_fake_client_stream_appends_failed_if_unterminated() -> None:
    from sagasmith.schemas.provider import TokenEvent

    client = DeterministicFakeClient(
        scripted_streams={"default": [TokenEvent(kind="token", text="hello")]}
    )
    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    events = list(client.stream(request))
    assert events[0].kind == "token"
    assert events[-1].kind == "failed"


@pytest.mark.smoke
def test_fake_client_module_has_no_network_imports() -> None:
    src = Path(fake_file).read_text(encoding="utf-8")
    assert "import http" not in src
    assert "import urllib" not in src
    assert "import httpx" not in src
    assert "import requests" not in src


def test_fake_client_cost_estimate_present() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    client = DeterministicFakeClient(
        {"default": make_fake_llm_response(text="hi", parsed_json=None)}
    )
    request = LLMRequest(
        agent_name="a",
        model="m",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    logs: list[object] = []
    response = invoke_with_retry(
        client,
        request,
        cheap_model="cheap",
        agent_name="a",
        turn_id=None,
        logger=logs.append,
    )
    assert response.cost_estimate_usd == 0.0


@pytest.mark.smoke
def test_invoke_with_retry_cheap_model_fallback_uses_fake_cheap() -> None:
    from sagasmith.evals.fixtures import make_fake_llm_response

    # We need a client where cheap_model returns valid JSON but default does not.
    # Since DeterministicFakeClient keys by agent_name, we can use a custom agent.
    class _ModelSwitchingFake:
        def complete(self, request: LLMRequest) -> object:
            if request.model == "fake-cheap":
                return make_fake_llm_response(text='{"ok":true}', parsed_json={"ok": True})
            return make_fake_llm_response(text="bad", parsed_json={"ok": "no"})

        def stream(self, request: LLMRequest) -> object:
            return iter([])

    req = LLMRequest(
        agent_name="a",
        model="fake-default",
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
    logs: list[object] = []
    response = invoke_with_retry(
        _ModelSwitchingFake(),  # type: ignore[arg-type]
        req,
        cheap_model="fake-cheap",
        agent_name="a",
        turn_id=None,
        logger=logs.append,
    )
    assert response.parsed_json == {"ok": True}
    assert any(log.retry_count == 2 for log in logs)
