"""HTTP transport Protocol and HttpxTransport implementation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class HttpResponse:
    """Normalized HTTP response for testability."""

    status_code: int
    text: str
    headers: dict[str, str]


class HttpTransport(Protocol):
    """Injectable HTTP transport abstraction."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> HttpResponse: ...

    def post_stream(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> Iterator[str]: ...


class HttpxTransport:
    """Httpx-based HttpTransport implementation."""

    def __init__(self, *, user_agent: str = "SagaSmith/0.0.1") -> None:
        self._client = httpx.Client(http2=False, headers={"User-Agent": user_agent})

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpxTransport:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> HttpResponse:
        response = self._client.post(
            url,
            json=json_body,
            headers=headers,
            timeout=timeout_seconds,
        )
        return HttpResponse(
            status_code=response.status_code,
            text=response.text,
            headers=dict(response.headers),
        )

    def post_stream(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> Iterator[str]:
        with self._client.stream(
            "POST",
            url,
            json=json_body,
            headers=headers,
            timeout=timeout_seconds,
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    yield line.removeprefix("data: ")
