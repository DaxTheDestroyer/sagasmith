"""Tests for fixture override re-validation (D-16)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sagasmith.evals.fixtures import (
    _with_overrides,
    make_valid_character_sheet,
    make_valid_player_profile,
)

pytestmark = pytest.mark.smoke


def test_fixture_override_rejects_invalid_hp() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_valid_character_sheet(current_hp=999)
    msg = str(exc_info.value)
    assert "current_hp" in msg
    assert "max_hp" in msg


def test_fixture_override_rejects_invalid_literal() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_valid_player_profile(pacing="lightspeed")
    assert "lightspeed" in str(exc_info.value) or "pacing" in str(exc_info.value)


def test_fixture_override_accepts_valid_changes() -> None:
    cs = make_valid_character_sheet(current_hp=15)
    assert cs.current_hp == 15


def test_fixture_override_empty_returns_original_instance() -> None:
    cs = make_valid_character_sheet()
    result = _with_overrides(cs, {})
    assert result is cs
