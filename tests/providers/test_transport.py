"""Tests for HttpTransport Protocol and HttpxTransport."""

from __future__ import annotations

import httpx

from sagasmith.providers.transport import HttpxTransport


def test_httpx_post_json_returns_status_and_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = HttpxTransport()
    # Replace the internal client with our mock transport client
    client._client = httpx.Client(transport=transport)

    response = client.post_json(
        url="https://example.com/api",
        headers={"Content-Type": "application/json"},
        json_body={"key": "value"},
        timeout_seconds=10,
    )
    assert response.status_code == 200
    assert "ok" in response.text


def test_httpx_post_json_non_2xx_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limited")

    transport = httpx.MockTransport(handler)
    client = HttpxTransport()
    client._client = httpx.Client(transport=transport)

    response = client.post_json(
        url="https://example.com/api",
        headers={},
        json_body={},
        timeout_seconds=10,
    )
    assert response.status_code == 429
    assert response.text == "Rate limited"


def test_httpx_post_stream_yields_data_lines_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='data: {"chunk":1}\n\ndata: [DONE]\n\nevent: ignore\n',
        )

    transport = httpx.MockTransport(handler)
    client = HttpxTransport()
    client._client = httpx.Client(transport=transport)

    lines = list(
        client.post_stream(
            url="https://example.com/api",
            headers={},
            json_body={},
            timeout_seconds=10,
        )
    )
    assert lines == ['{"chunk":1}', "[DONE]"]


def test_httpx_transport_sets_user_agent() -> None:
    client = HttpxTransport()
    assert client._client.headers["User-Agent"] == "SagaSmith/0.0.1"
