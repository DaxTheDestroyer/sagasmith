"""Tests for provider schema models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from sagasmith.schemas import (
    CompletedEvent,
    FailedEvent,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderLogRecord,
    TokenEvent,
    TokenUsage,
    UsageUpdateEvent,
)
from sagasmith.schemas.export import export_all_schemas
from sagasmith.services.secrets import SecretRef


def test_llm_request_rejects_json_schema_without_schema() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(
            agent_name="a",
            model="m",
            messages=[],
            response_format="json_schema",
            json_schema=None,
            temperature=0.0,
            timeout_seconds=10,
        )


def test_llm_request_rejects_text_with_schema() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(
            agent_name="a",
            model="m",
            messages=[],
            response_format="text",
            json_schema={"type": "object"},
            temperature=0.0,
            timeout_seconds=10,
        )


def test_llm_request_text_round_trip() -> None:
    req = LLMRequest(
        agent_name="a",
        model="m",
        messages=[],
        response_format="text",
        temperature=0.0,
        timeout_seconds=10,
    )
    dumped = req.model_dump(mode="json")
    restored = LLMRequest.model_validate(dumped)
    assert restored.agent_name == "a"


def test_llm_request_json_schema_round_trip() -> None:
    req = LLMRequest(
        agent_name="a",
        model="m",
        messages=[],
        response_format="json_schema",
        json_schema={"type": "object"},
        temperature=0.0,
        timeout_seconds=10,
    )
    dumped = req.model_dump(mode="json")
    restored = LLMRequest.model_validate(dumped)
    assert restored.json_schema == {"type": "object"}


def test_token_usage_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=-1, completion_tokens=0, total_tokens=0)
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=-0.01)


def test_llm_response_round_trip() -> None:
    usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    resp = LLMResponse(text="hi", usage=usage, finish_reason="stop")
    dumped = resp.model_dump(mode="json")
    restored = LLMResponse.model_validate(dumped)
    assert restored.parsed_json is None

    resp2 = LLMResponse(text='{"a":1}', parsed_json={"a": 1}, usage=usage, finish_reason="stop")
    assert LLMResponse.model_validate(resp2.model_dump(mode="json")).parsed_json == {"a": 1}


def test_stream_event_variants_round_trip() -> None:
    usage = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    resp = LLMResponse(text="hi", usage=usage, finish_reason="stop")

    token_event = TokenEvent(kind="token", text="hello")
    usage_event = UsageUpdateEvent(kind="usage_update", usage=usage)
    completed_event = CompletedEvent(kind="completed", response=resp)
    failed_event = FailedEvent(kind="failed", failure_kind="other", message="oops")

    assert TokenEvent.model_validate(token_event.model_dump(mode="json")).kind == "token"
    assert (
        UsageUpdateEvent.model_validate(usage_event.model_dump(mode="json")).kind == "usage_update"
    )
    assert (
        CompletedEvent.model_validate(completed_event.model_dump(mode="json")).kind == "completed"
    )
    assert FailedEvent.model_validate(failed_event.model_dump(mode="json")).kind == "failed"


def test_provider_config_rejects_openrouter_without_key() -> None:
    with pytest.raises(ValidationError):
        ProviderConfig(
            provider="openrouter",
            api_key_ref=None,
            default_model="m",
            narration_model="m",
            cheap_model="m",
            pricing_mode="static_table",
        )


def test_provider_config_rejects_fake_with_key() -> None:
    with pytest.raises(ValidationError):
        ProviderConfig(
            provider="fake",
            api_key_ref=SecretRef(kind="env", name="KEY"),
            default_model="m",
            narration_model="m",
            cheap_model="m",
            pricing_mode="static_table",
        )


def test_provider_log_record_rejects_negative_retry() -> None:
    with pytest.raises(ValidationError):
        ProviderLogRecord(
            provider="fake",
            model="m",
            agent_name="a",
            request_id="r1",
            failure_kind="none",
            retry_count=-1,
            latency_ms=0,
            response_hash="abc",
            timestamp="2026-04-26T12:00:00Z",
        )


def test_provider_log_record_rejects_negative_latency() -> None:
    with pytest.raises(ValidationError):
        ProviderLogRecord(
            provider="fake",
            model="m",
            agent_name="a",
            request_id="r1",
            failure_kind="none",
            retry_count=0,
            latency_ms=-1,
            response_hash="abc",
            timestamp="2026-04-26T12:00:00Z",
        )


@pytest.mark.smoke
def test_schema_export_count_is_25(tmp_path: Path) -> None:
    from pathlib import Path

    out = Path(tmp_path) / "schemas"
    paths = export_all_schemas(out)
    # Phase 8 added RetconAuditRecord and VaultWriteAuditRecord (total: 31).
    assert len(paths) == 31
    names = {p.name.removesuffix(".schema.json") for p in paths}
    assert "LLMRequest" in names
    assert "LLMResponse" in names
    assert "ProviderConfig" in names
    assert "ProviderLogRecord" in names
    assert "CostLogRecord" in names
    assert "TurnRecord" in names
    assert "CheckpointRef" in names
    assert "TranscriptEntry" in names
    assert "StateDeltaRecord" in names
