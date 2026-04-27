"""Fake HTTP transport for provider unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sagasmith.providers.transport import HttpResponse


@dataclass
class FakeHttpTransport:
    """Test double implementing HttpTransport Protocol."""

    scripted_json: dict[str, HttpResponse] = field(default_factory=dict)
    scripted_stream_lines: dict[str, list[str]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> HttpResponse:
        self.calls.append(
            {
                "method": "post_json",
                "url": url,
                "headers": headers,
                "json_body": json_body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.scripted_json.get(url, HttpResponse(status_code=500, text="", headers={}))

    def post_stream(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: int,
    ) -> Iterator[str]:
        self.calls.append(
            {
                "method": "post_stream",
                "url": url,
                "headers": headers,
                "json_body": json_body,
                "timeout_seconds": timeout_seconds,
            }
        )
        yield from self.scripted_stream_lines.get(url, [])
