"""Static pricing table loader and cost estimation helper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PriceEntry:
    """Price for a provider/model pair in USD per 1000 tokens."""

    prompt_usd_per_1k: float
    completion_usd_per_1k: float

    def __post_init__(self) -> None:
        if self.prompt_usd_per_1k <= 0:
            raise ValueError(f"prompt_usd_per_1k must be > 0, got {self.prompt_usd_per_1k}")
        if self.completion_usd_per_1k <= 0:
            raise ValueError(f"completion_usd_per_1k must be > 0, got {self.completion_usd_per_1k}")


def load_pricing_table(path: Path | None = None) -> dict[str, PriceEntry]:
    """Load the bundled pricing table from JSON.

    Raises FileNotFoundError when an explicit path is missing.
    """
    if path is None:
        path = Path(__file__).parent / "pricing_table.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, PriceEntry] = {}
    for key, entry in data.items():
        prompt = entry.get("prompt_usd_per_1k", 0)
        completion = entry.get("completion_usd_per_1k", 0)
        if prompt <= 0 or completion <= 0:
            raise ValueError(f"invalid pricing table entry: {key}")
        result[key] = PriceEntry(prompt_usd_per_1k=prompt, completion_usd_per_1k=completion)
    return result


def estimate_cost_from_usage(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    table: dict[str, PriceEntry],
) -> tuple[float, bool]:
    """Estimate cost from token usage using the static pricing table.

    Returns (cost_usd, is_approximate). Raises KeyError if the provider/model
    is not present in the table.
    """
    key = f"{provider}/{model}"
    entry = table[key]
    cost = (
        prompt_tokens / 1000 * entry.prompt_usd_per_1k
        + completion_tokens / 1000 * entry.completion_usd_per_1k
    )
    return cost, True
