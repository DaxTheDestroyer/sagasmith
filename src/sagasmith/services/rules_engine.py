"""Deterministic first-slice rules resolution services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sagasmith.schemas.mechanics import CharacterSheet, CheckProposal, CheckResult
from sagasmith.services.dice import DiceService
from sagasmith.services.pf2e import compute_degree

CheckKind = Literal["skill", "initiative"]


@dataclass(frozen=True)
class RulesEngine:
    """Resolve first-slice checks from typed sheet data and deterministic dice."""

    dice: DiceService

    def build_check_proposal(
        self,
        sheet: CharacterSheet,
        *,
        stat: str,
        dc: int,
        reason: str,
        kind: CheckKind = "skill",
        target_id: str | None = None,
    ) -> CheckProposal:
        """Build a deterministic check proposal without rolling."""

        return self._build_check_proposal(
            sheet,
            stat=stat,
            dc=dc,
            reason=reason,
            roll_index=0,
            kind=kind,
            target_id=target_id,
        )

    def resolve_check(
        self,
        sheet: CharacterSheet,
        *,
        stat: str,
        dc: int,
        reason: str,
        roll_index: int,
        kind: CheckKind = "skill",
        target_id: str | None = None,
    ) -> CheckResult:
        """Resolve a skill or Perception check with auditable deterministic output."""

        proposal = self._build_check_proposal(
            sheet,
            stat=stat,
            dc=dc,
            reason=reason,
            roll_index=roll_index,
            kind=kind,
            target_id=target_id,
        )
        roll_result = self.dice.roll_d20(
            purpose=stat,
            actor_id=sheet.id,
            modifier=proposal.modifier,
            roll_index=roll_index,
            dc=dc,
        )
        degree = compute_degree(natural=roll_result.natural, total=roll_result.total, dc=dc)
        return CheckResult(
            proposal_id=proposal.id,
            roll_result=roll_result,
            degree=degree,
            effects=[],
            state_deltas=[],
        )

    def _build_check_proposal(
        self,
        sheet: CharacterSheet,
        *,
        stat: str,
        dc: int,
        reason: str,
        roll_index: int,
        kind: CheckKind,
        target_id: str | None,
    ) -> CheckProposal:
        modifier = _lookup_modifier(sheet, stat)
        return CheckProposal(
            id=f"check_{stat}_{roll_index:06d}",
            reason=reason,
            kind=kind,
            actor_id=sheet.id,
            target_id=target_id,
            stat=stat,
            modifier=modifier,
            dc=dc,
            secret=False,
        )


def _lookup_modifier(sheet: CharacterSheet, stat: str) -> int:
    if stat == "perception":
        return sheet.perception_modifier
    if stat in sheet.skills:
        return sheet.skills[stat]
    raise ValueError(f"unsupported check stat {stat!r}")
