"""Provider Runtime: build a live LLM adapter from persisted provider settings."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from sagasmith.app.config import SettingsRepository
from sagasmith.providers.client import LLMClient
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.providers.openrouter import OpenRouterClient
from sagasmith.providers.transport import HttpTransport, HttpxTransport
from sagasmith.schemas.campaign import ProviderSettings
from sagasmith.schemas.provider import (
    CompletedEvent,
    LLMResponse,
    ProviderConfig,
    TokenEvent,
    TokenUsage,
)
from sagasmith.services.errors import SecretRefError
from sagasmith.services.secrets import SecretRef, resolve_secret

ProviderStartupErrorKind = Literal[
    "missing_settings",
    "invalid_settings",
    "secret_unavailable",
    "unsupported_provider",
]


@dataclass(frozen=True)
class ProviderStartupError:
    """Safe, typed provider startup failure."""

    kind: ProviderStartupErrorKind
    provider: str | None
    message: str
    detail: str | None = None
    can_continue_without_llm: bool = False


@dataclass(frozen=True)
class ProviderRuntime:
    """A live provider adapter plus the validated provider configuration."""

    settings: ProviderSettings
    config: ProviderConfig
    client: LLMClient


@dataclass(frozen=True)
class ProviderRuntimeResult:
    """Result of building Provider Runtime without raising raw startup exceptions."""

    runtime: ProviderRuntime | None = None
    error: ProviderStartupError | None = None

    @property
    def is_ready(self) -> bool:
        return self.runtime is not None and self.error is None


def build_provider_runtime(
    conn: sqlite3.Connection,
    campaign_id: str,
    *,
    fake_client: LLMClient | None = None,
    transport: HttpTransport | None = None,
    preflight_secrets: bool = True,
) -> ProviderRuntimeResult:
    """Build the LLM adapter for a campaign from persisted provider settings."""

    try:
        settings = SettingsRepository(conn).get_provider_settings(campaign_id)
    except Exception as exc:
        return ProviderRuntimeResult(
            error=ProviderStartupError(
                kind="invalid_settings",
                provider=None,
                message="Provider settings could not be loaded.",
                detail=_safe_detail(exc),
            )
        )

    if settings is None:
        return ProviderRuntimeResult(
            error=ProviderStartupError(
                kind="missing_settings",
                provider=None,
                message="Provider settings are missing. Run `sagasmith configure` before play.",
            )
        )

    if settings.provider == "fake":
        config = _provider_config_from_settings(settings, api_key_ref=None)
        client = fake_client if fake_client is not None else _default_fake_client()
        return ProviderRuntimeResult(
            runtime=ProviderRuntime(settings=settings, config=config, client=client)
        )

    if settings.provider == "openrouter":
        if settings.api_key_ref is None:
            return ProviderRuntimeResult(
                error=ProviderStartupError(
                    kind="invalid_settings",
                    provider="openrouter",
                    message="OpenRouter provider settings are missing an API key reference.",
                )
            )
        if preflight_secrets:
            secret: str | None = None
            try:
                secret = resolve_secret(settings.api_key_ref)
            except SecretRefError as exc:
                return ProviderRuntimeResult(
                    error=ProviderStartupError(
                        kind="secret_unavailable",
                        provider="openrouter",
                        message=(
                            "OpenRouter credentials could not be resolved. "
                            "Run `sagasmith configure --api-key-ref env:VAR` with a set env var."
                        ),
                        detail=f"{exc.ref_kind}: {exc.reason}",
                    )
                )
            finally:
                del secret
        config = _provider_config_from_settings(settings, api_key_ref=settings.api_key_ref)
        client = OpenRouterClient(config, transport=transport or HttpxTransport())
        return ProviderRuntimeResult(
            runtime=ProviderRuntime(settings=settings, config=config, client=client)
        )

    return ProviderRuntimeResult(
        error=ProviderStartupError(
            kind="unsupported_provider",
            provider=str(settings.provider),
            message=f"Unsupported provider: {settings.provider}",
        )
    )


def _provider_config_from_settings(
    settings: ProviderSettings,
    *,
    api_key_ref: SecretRef | None,
) -> ProviderConfig:
    return ProviderConfig(
        provider=settings.provider,
        api_key_ref=api_key_ref,
        default_model=settings.default_model,
        narration_model=settings.narration_model,
        cheap_model=settings.cheap_model,
        pricing_mode=settings.pricing_mode,
    )


def _default_fake_client() -> DeterministicFakeClient:
    text = "The scene shifts. A new detail draws your attention."
    response = LLMResponse(
        text=text,
        parsed_json={"verdict": "pass", "reason": None, "violated_term": None},
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        finish_reason="stop",
        cost_estimate_usd=0.0,
    )
    return DeterministicFakeClient(
        scripted_responses={"default": response},
        scripted_streams={
            "default": [
                TokenEvent(kind="token", text=text),
                CompletedEvent(kind="completed", response=response),
            ]
        },
    )


def _safe_detail(exc: Exception) -> str:
    text = str(exc)
    return text[:200] if text else exc.__class__.__name__
