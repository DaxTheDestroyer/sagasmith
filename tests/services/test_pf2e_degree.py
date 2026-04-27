"""Tests for PF2e degree-of-success computation."""

from __future__ import annotations

import pytest

from sagasmith.services.pf2e import compute_degree


def test_success_exact_dc() -> None:
    assert compute_degree(natural=10, total=15, dc=15) == "success"


def test_failure_one_under_dc() -> None:
    assert compute_degree(natural=10, total=14, dc=15) == "failure"


def test_critical_success_exact_plus_ten() -> None:
    assert compute_degree(natural=10, total=25, dc=15) == "critical_success"


def test_critical_failure_exact_minus_ten() -> None:
    assert compute_degree(natural=10, total=5, dc=15) == "critical_failure"


def test_success_one_under_crit_threshold() -> None:
    assert compute_degree(natural=10, total=24, dc=15) == "success"


def test_critical_failure_below_minus_ten() -> None:
    assert compute_degree(natural=10, total=4, dc=15) == "critical_failure"


@pytest.mark.smoke
def test_natural_twenty_bumps_failure_to_success() -> None:
    assert compute_degree(natural=20, total=14, dc=15) == "success"


@pytest.mark.smoke
def test_natural_twenty_bumps_success_to_critical() -> None:
    assert compute_degree(natural=20, total=15, dc=15) == "critical_success"


def test_natural_twenty_on_critical_stays() -> None:
    assert compute_degree(natural=20, total=25, dc=15) == "critical_success"


def test_natural_twenty_on_critical_failure_to_failure() -> None:
    assert compute_degree(natural=20, total=4, dc=15) == "failure"


def test_natural_one_on_critical_success_to_success() -> None:
    assert compute_degree(natural=1, total=25, dc=15) == "success"


def test_natural_one_on_success_to_failure() -> None:
    assert compute_degree(natural=1, total=15, dc=15) == "failure"


def test_natural_one_on_failure_to_critical_failure() -> None:
    assert compute_degree(natural=1, total=14, dc=15) == "critical_failure"


def test_natural_one_on_critical_failure_stays() -> None:
    assert compute_degree(natural=1, total=4, dc=15) == "critical_failure"


def test_natural_out_of_range_rejects() -> None:
    with pytest.raises(ValueError):
        compute_degree(natural=0, total=15, dc=15)
    with pytest.raises(ValueError):
        compute_degree(natural=21, total=15, dc=15)
