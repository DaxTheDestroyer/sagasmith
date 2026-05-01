"""Provider abstractions: protocol, retry ladder, fake, logging, transport."""

from sagasmith.providers.client import LLMClient, invoke_with_retry
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.providers.logging import build_provider_log_record
from sagasmith.providers.openrouter import OpenRouterClient
from sagasmith.providers.runtime import (
    ProviderRuntime,
    ProviderRuntimeResult,
    ProviderStartupError,
    build_provider_runtime,
)
from sagasmith.providers.transport import HttpResponse, HttpTransport, HttpxTransport

__all__ = [
    "DeterministicFakeClient",
    "HttpResponse",
    "HttpTransport",
    "HttpxTransport",
    "LLMClient",
    "OpenRouterClient",
    "ProviderRuntime",
    "ProviderRuntimeResult",
    "ProviderStartupError",
    "build_provider_log_record",
    "build_provider_runtime",
    "invoke_with_retry",
]
