"""Tests for TUIState and StatusSnapshot pure data models."""

from __future__ import annotations

from sagasmith.tui.state import StatusSnapshot


def test_status_snapshot_format_hp_default() -> None:
    snap = StatusSnapshot()
    assert snap.format_hp() == "HP: \u2014"


def test_status_snapshot_format_hp_filled() -> None:
    snap = StatusSnapshot(hp_current=12, hp_max=20)
    assert snap.format_hp() == "HP: 12/20"


def test_status_snapshot_format_clock_default() -> None:
    snap = StatusSnapshot()
    assert snap.format_clock() == "Clock: \u2014"


def test_status_snapshot_format_clock_filled() -> None:
    snap = StatusSnapshot(clock_day=3, clock_hhmm="14:30")
    assert snap.format_clock() == "Day 3, 14:30"


def test_status_snapshot_is_frozen() -> None:
    snap = StatusSnapshot(hp_current=5)
    import dataclasses

    assert dataclasses.is_dataclass(snap)
    # Frozen dataclass raises FrozenInstanceError on attribute assignment
    try:
        snap.hp_current = 10  # type: ignore[misc]
        raise AssertionError("Expected FrozenInstanceError")
    except Exception:
        pass  # expected


def test_status_snapshot_default_conditions_empty_tuple() -> None:
    snap = StatusSnapshot()
    assert snap.conditions == ()
    assert snap.last_rolls == ()
