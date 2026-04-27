"""Deterministic fake LLMClient for offline tests and smoke."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from sagasmith.schemas.provider import (
    CompletedEvent,
    FailedEvent,
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
)


@dataclass(frozen=True)
class DeterministicFakeClient:
    """Fake LLMClient that returns scripted responses and streams."""

    scripted_responses: dict[str, LLMResponse] = field(default_factory=dict[str, LLMResponse])
    scripted_streams: dict[str, list[LLMStreamEvent]] = field(
        default_factory=dict[str, list[LLMStreamEvent]]
    )

    def complete(self, request: LLMRequest) -> LLMResponse:
        key = request.agent_name if request.agent_name in self.scripted_responses else "default"
        if key not in self.scripted_responses:
            raise KeyError(f"fake: no scripted response for agent {request.agent_name!r}")
        return self.scripted_responses[key]

    def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]:
        key = request.agent_name if request.agent_name in self.scripted_streams else "default"
        events = list(self.scripted_streams.get(key, []))
        if not events:
            yield FailedEvent(
                kind="failed",
                failure_kind="other",
                message="fake: stream did not terminate",
            )
            return
        yield from events
        if events and not isinstance(events[-1], (CompletedEvent, FailedEvent)):
            yield FailedEvent(
                kind="failed",
                failure_kind="other",
                message="fake: stream did not terminate",
            )
