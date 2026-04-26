"""Schema round-trip assertions shared by smoke and eval tests."""

from __future__ import annotations

import json
from pathlib import Path

import pydantic

from sagasmith.schemas.validation import PersistedStateError, validate_persisted_state


def assert_round_trip(instance: pydantic.BaseModel) -> None:
    """Assert a Pydantic model survives JSON-mode dump and validation."""

    data = instance.model_dump(mode="json")
    rebuilt = type(instance).model_validate(data)
    assert rebuilt == instance, (
        f"Round-trip mismatch for {type(instance).__name__}. "
        "Original and rebuilt differ; inspect model_dump output."
    )


def assert_fixture_round_trips(path: Path) -> None:
    """Assert a committed persisted-state fixture validates and round-trips."""

    data = json.loads(path.read_text(encoding="utf-8"))
    state = validate_persisted_state(data)
    roundtrip = validate_persisted_state(state.model_dump(mode="json"))
    assert roundtrip == state


def assert_fixture_rejects(path: Path, expected_substring: str) -> None:
    """Assert a committed persisted-state fixture fails validation clearly."""

    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_persisted_state(data)
    except PersistedStateError as exc:
        assert expected_substring in str(exc), (
            f"Expected {expected_substring!r} in rejection message; got {exc!s}"
        )
        return
    raise AssertionError(f"Fixture {path.name} should have been rejected but validated")
