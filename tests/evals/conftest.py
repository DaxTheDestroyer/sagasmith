"""Shared eval fixture paths."""

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def valid_state_path() -> Path:
    return FIXTURE_DIR / "valid_saga_state.json"


@pytest.fixture
def missing_field_path() -> Path:
    return FIXTURE_DIR / "invalid_saga_state_missing_field.json"


@pytest.fixture
def bad_enum_path() -> Path:
    return FIXTURE_DIR / "invalid_saga_state_bad_enum.json"


@pytest.fixture
def redaction_sample_text() -> str:
    return (FIXTURE_DIR / "secret_redaction_sample.txt").read_text(encoding="utf-8")
