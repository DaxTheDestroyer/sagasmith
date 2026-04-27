"""LLMClient Protocol and retry-ladder helper."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from time import perf_counter_ns
from typing import Protocol

import jsonschema

from sagasmith.schemas.provider import (
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
    ProviderLogRecord,
)
from sagasmith.services.errors import ProviderCallError

from .logging import build_provider_log_record


class LLMClient(Protocol):
    """Model-agnostic abstraction for structured and streaming LLM calls."""

    def complete(self, request: LLMRequest) -> LLMResponse: ...
    def stream(self, request: LLMRequest) -> Iterator[LLMStreamEvent]: ...


class _SchemaViolation(Exception):
    """Internal: parsed_json failed schema validation."""


def _validate_parsed_json(parsed_json: object, schema: dict[str, object]) -> None:
    try:
        jsonschema.validate(instance=parsed_json, schema=schema)
    except jsonschema.ValidationError as exc:
        raise _SchemaViolation(str(exc)) from exc


def invoke_with_retry(
    client: LLMClient,
    request: LLMRequest,
    *,
    cheap_model: str,
    agent_name: str,
    turn_id: str | None,
    logger: Callable[[ProviderLogRecord], None],
    clock: Callable[[], datetime] | None = None,
) -> LLMResponse:
    """Call client.complete with the D-03 retry ladder.

    - Schema validation failures: retry up to 3 times (same model, same model, cheap model).
    - Network timeout / rate limit: single retry with same model.
    """
    from datetime import datetime

    def _now() -> datetime:
        return datetime.now()

    now = clock if clock is not None else _now

    def _emit(
        *,
        model: str,
        response: LLMResponse | None,
        failure_kind: str,
        retry_count: int,
        latency_ms: int,
    ) -> None:
        text = response.text if response else ""
        record = build_provider_log_record(
            provider="fake",
            model=model,
            agent_name=agent_name,
            turn_id=turn_id,
            request_id=uuid.uuid4().hex,
            provider_response_id=response.provider_response_id if response else None,
            failure_kind=failure_kind,
            retry_count=retry_count,
            usage=response.usage if response else None,
            cost_estimate_usd=response.cost_estimate_usd if response else None,
            latency_ms=latency_ms,
            response_text=text,
            clock=now,
        )
        logger(record)

    def _call(req: LLMRequest, retry_count: int) -> LLMResponse:
        start = perf_counter_ns()
        try:
            response = client.complete(req)
        except Exception as exc:
            latency = (perf_counter_ns() - start) // 1_000_000
            failure_kind = getattr(exc, "failure_kind", "other")
            _emit(
                model=req.model,
                response=None,
                failure_kind=failure_kind,
                retry_count=retry_count,
                latency_ms=latency,
            )
            raise

        latency = (perf_counter_ns() - start) // 1_000_000
        if req.response_format == "json_schema" and req.json_schema is not None:
            try:
                _validate_parsed_json(response.parsed_json, req.json_schema)
            except _SchemaViolation as exc:
                _emit(
                    model=req.model,
                    response=response,
                    failure_kind="schema_validation",
                    retry_count=retry_count,
                    latency_ms=latency,
                )
                raise _SchemaViolation("schema validation failed") from exc

        _emit(
            model=req.model,
            response=response,
            failure_kind="none",
            retry_count=retry_count,
            latency_ms=latency,
        )
        return response

    # Attempt 1
    try:
        return _call(request, 0)
    except _SchemaViolation:
        pass
    except Exception as exc:
        failure_kind = getattr(exc, "failure_kind", None)
        if failure_kind in {"network_timeout", "rate_limit"}:
            try:
                return _call(request, 1)
            except Exception as exc2:
                raise ProviderCallError(
                    f"{failure_kind} retry failed for agent={agent_name} model={request.model}"
                ) from exc2
        raise

    # Attempt 2 (same model repair)
    try:
        return _call(request, 1)
    except _SchemaViolation:
        pass

    # Attempt 3 (cheap model)
    cheap_request = request.model_copy(update={"model": cheap_model})
    try:
        return _call(cheap_request, 2)
    except _SchemaViolation:
        pass

    # Exhausted
    _emit(
        model=request.model,
        response=None,
        failure_kind="schema_validation",
        retry_count=3,
        latency_ms=0,
    )
    raise ProviderCallError(
        f"schema_validation exhausted retry ladder for agent={agent_name} model={request.model}"
    )
