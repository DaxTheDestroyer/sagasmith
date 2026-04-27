"""Metadata-only provider log builder with redaction pass."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime

from sagasmith.evals.redaction import RedactionCanary
from sagasmith.schemas.provider import ProviderLogRecord, TokenUsage


def build_provider_log_record(
    *,
    provider: str,
    model: str,
    agent_name: str,
    turn_id: str | None,
    request_id: str,
    provider_response_id: str | None,
    failure_kind: str,
    retry_count: int,
    usage: TokenUsage | None,
    cost_estimate_usd: float | None,
    latency_ms: int,
    response_text: str,
    clock: Callable[[], datetime] | None = None,
) -> ProviderLogRecord:
    """Build a metadata-only ProviderLogRecord.

    safe_snippet is set only when RedactionCanary.scan returns zero hits.
    response_hash is always safe to log.
    """
    now = clock if clock is not None else datetime.now

    if response_text:
        response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()[:16]
    else:
        response_hash = "empty"

    snippet = response_text[:120] if response_text else None
    safe_snippet = snippet if snippet and not RedactionCanary().scan(snippet) else None

    return ProviderLogRecord(
        provider=provider,  # type: ignore[arg-type]
        model=model,
        agent_name=agent_name,
        turn_id=turn_id,
        request_id=request_id,
        provider_response_id=provider_response_id,
        failure_kind=failure_kind,  # type: ignore[arg-type]
        retry_count=retry_count,
        usage=usage,
        cost_estimate_usd=cost_estimate_usd,
        latency_ms=latency_ms,
        safe_snippet=safe_snippet,
        response_hash=response_hash,
        timestamp=now().isoformat(),
    )
