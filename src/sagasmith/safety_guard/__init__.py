"""Safety Guard Module: one safety Interface for play-turn content policy."""

from .guard import (
    DEFAULT_FALLBACK_NARRATION,
    DEFAULT_MAX_REWRITES,
    GeneratedAllowed,
    GeneratedFallback,
    GeneratedProseDecision,
    GeneratedRewrite,
    IntentAllowed,
    IntentBlocked,
    IntentDecision,
    IntentRerouted,
    RetryDecision,
    SafetyGuard,
    StreamHit,
)

__all__ = [
    "DEFAULT_FALLBACK_NARRATION",
    "DEFAULT_MAX_REWRITES",
    "GeneratedAllowed",
    "GeneratedFallback",
    "GeneratedProseDecision",
    "GeneratedRewrite",
    "IntentAllowed",
    "IntentBlocked",
    "IntentDecision",
    "IntentRerouted",
    "RetryDecision",
    "SafetyGuard",
    "StreamHit",
]
