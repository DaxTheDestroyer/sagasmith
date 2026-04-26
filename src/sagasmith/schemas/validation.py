"""Persisted SagaState validation gate."""

from __future__ import annotations

from typing import Any

import pydantic

from .saga_state import SagaState


class PersistedStateError(Exception):
    """Raised when persisted state fails validation before graph consumption."""


def validate_persisted_state(data: Any) -> SagaState:
    """Validate untrusted persisted state before graph nodes can consume it."""

    if not isinstance(data, dict):
        raise PersistedStateError(f"Persisted state must be a dict, got {type(data).__name__}")
    try:
        return SagaState.model_validate(data)
    except pydantic.ValidationError as exc:
        raise PersistedStateError(str(exc)) from exc
