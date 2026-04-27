"""Pure PF2e degree-of-success math."""

from __future__ import annotations

from typing import Literal

Degree = Literal["critical_success", "success", "failure", "critical_failure"]
_LADDER: tuple[Degree, ...] = ("critical_failure", "failure", "success", "critical_success")


def compute_degree(natural: int, total: int, dc: int) -> Degree:
    """Return the PF2e degree of success given natural roll, total, and DC.

    Natural 20 raises degree by one; natural 1 lowers degree by one.
    """
    if not 1 <= natural <= 20:
        raise ValueError(f"natural must be in 1..20, got {natural}")

    if total >= dc + 10:
        base_idx = 3
    elif total >= dc:
        base_idx = 2
    elif total <= dc - 10:
        base_idx = 0
    else:
        base_idx = 1

    if natural == 20:
        idx = min(3, base_idx + 1)
    elif natural == 1:
        idx = max(0, base_idx - 1)
    else:
        idx = base_idx

    return _LADDER[idx]
