"""Tests for pricing table loader and cost estimator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sagasmith.services.pricing_table import (
    estimate_cost_from_usage,
    load_pricing_table,
)


def test_load_pricing_table_loads_bundled_file() -> None:
    table = load_pricing_table()
    assert len(table) == 5
    assert "fake/fake-default" in table
    assert "openrouter/openai/gpt-4o-mini" in table


def test_load_pricing_table_rejects_zero_price(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"bad/model": {"prompt_usd_per_1k": 0, "completion_usd_per_1k": 0.001}})
    )
    with pytest.raises(ValueError):
        load_pricing_table(path)


def test_estimate_cost_matches_expected() -> None:
    table = load_pricing_table()
    cost, approx = estimate_cost_from_usage(
        provider="fake",
        model="fake-default",
        prompt_tokens=1000,
        completion_tokens=500,
        table=table,
    )
    assert cost == pytest.approx(0.002)
    assert approx is True


def test_estimate_cost_missing_key_raises() -> None:
    table = load_pricing_table()
    with pytest.raises(KeyError):
        estimate_cost_from_usage(
            provider="unknown",
            model="model",
            prompt_tokens=100,
            completion_tokens=100,
            table=table,
        )


def test_estimate_cost_zero_tokens_is_zero() -> None:
    table = load_pricing_table()
    cost, approx = estimate_cost_from_usage(
        provider="fake",
        model="fake-default",
        prompt_tokens=0,
        completion_tokens=0,
        table=table,
    )
    assert cost == 0.0
    assert approx is True
