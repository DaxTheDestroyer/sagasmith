"""Seeded deterministic DiceService."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sagasmith.schemas.mechanics import RollResult

_DIE_PATTERN = re.compile(r"^d(\d+)$")


@dataclass(frozen=True)
class DiceService:
    """Deterministic dice roller seeded by campaign + session identifiers."""

    campaign_seed: str
    session_seed: str
    clock: Callable[[], datetime] = datetime.now

    def roll_d20(
        self,
        *,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        return self.roll(
            die="d20",
            purpose=purpose,
            actor_id=actor_id,
            modifier=modifier,
            roll_index=roll_index,
            dc=dc,
        )

    def roll(
        self,
        *,
        die: str,
        purpose: str,
        actor_id: str,
        modifier: int,
        roll_index: int,
        dc: int | None = None,
    ) -> RollResult:
        match = _DIE_PATTERN.match(die)
        if match is None:
            raise ValueError(f"die must match 'd<N>', got {die!r}")
        sides = int(match.group(1))
        if not 2 <= sides <= 1000:
            raise ValueError(f"die sides must be in 2..1000, got {sides}")

        key = f"{self.campaign_seed}|{self.session_seed}|{purpose}|{actor_id}|{roll_index}".encode()
        digest = hashlib.sha256(key).digest()
        n = int.from_bytes(digest[:8], "big")
        natural = (n % sides) + 1
        total = natural + modifier
        roll_id = f"roll_{purpose}_{actor_id}_{roll_index:06d}"
        return RollResult(
            roll_id=roll_id,
            seed=f"{self.campaign_seed}:{self.session_seed}",
            die=die,
            natural=natural,
            modifier=modifier,
            total=total,
            dc=dc,
            timestamp=self.clock().isoformat(),
        )
