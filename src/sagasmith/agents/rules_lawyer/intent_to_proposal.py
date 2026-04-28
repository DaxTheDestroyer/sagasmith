"""Convert resolved player intent into deterministic mechanics proposals."""

from __future__ import annotations

from typing import Any

from sagasmith.schemas.mechanics import CharacterSheet, CheckProposal, CombatState
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.intent_resolution import IntentCandidate, resolve_intents
from sagasmith.services.rules_engine import RulesEngine


def intents_to_proposals(
    player_input: str,
    *,
    scene_context: dict[str, Any] | None,
    character_sheet: CharacterSheet,
    rules_engine: RulesEngine,
    combat_engine: CombatEngine,
    combat_state: CombatState | None = None,
    services: Any | None = None,
    roll_index: int = 0,
) -> list[CheckProposal]:
    """Resolve player input and return schema-validated CheckProposal values.

    LLM fallback may identify action shape through ``resolve_intents`` when a
    client is present, but every modifier/DC is rebuilt here from deterministic
    sheet/combat state.
    """

    candidates = resolve_intents(
        player_input,
        scene_context=scene_context,
        llm_client=getattr(services, "llm", None),
        cost_governor=getattr(services, "cost", None),
        turn_id=(scene_context or {}).get("turn_id") if isinstance(scene_context, dict) else None,
    )
    return proposals_from_candidates(
        candidates,
        character_sheet=character_sheet,
        rules_engine=rules_engine,
        combat_engine=combat_engine,
        combat_state=combat_state,
        roll_index=roll_index,
    )


def proposals_from_candidates(
    candidates: list[IntentCandidate],
    *,
    character_sheet: CharacterSheet,
    rules_engine: RulesEngine,
    combat_engine: CombatEngine,
    combat_state: CombatState | None = None,
    roll_index: int = 0,
) -> list[CheckProposal]:
    """Build deterministic proposals for proposal-bearing intent candidates."""

    proposals: list[CheckProposal] = []
    for candidate in candidates:
        if candidate.action == "skill_check" and candidate.stat is not None and candidate.dc is not None:
            proposals.append(
                rules_engine.build_check_proposal(
                    character_sheet,
                    stat=candidate.stat,
                    dc=candidate.dc,
                    reason=candidate.reason,
                    roll_index=roll_index + len(proposals),
                )
            )
        elif candidate.action == "strike" and combat_state is not None:
            proposal = _attack_proposal(candidate, character_sheet, combat_state, roll_index + len(proposals))
            if proposal is not None:
                proposals.append(proposal)
        elif candidate.action == "start_combat":
            # Initiative proposals are created by CombatEngine.start_encounter when executed.
            continue
    # `combat_engine` is accepted to make the deterministic dependency explicit for callers.
    _ = combat_engine
    return [CheckProposal.model_validate(proposal.model_dump()) for proposal in proposals]


def _attack_proposal(
    candidate: IntentCandidate,
    character_sheet: CharacterSheet,
    combat_state: CombatState,
    roll_index: int,
) -> CheckProposal | None:
    if candidate.target_id is None or candidate.attack_id is None:
        return None
    attack = next((item for item in character_sheet.attacks if item.id == candidate.attack_id), None)
    target = next((item for item in combat_state.combatants if item.id == candidate.target_id), None)
    if attack is None or target is None:
        return None
    dc = target.armor_class + (2 if combat_state.positions.get(target.id) == "behind_cover" else 0)
    return CheckProposal(
        id=f"check_attack_{attack.id}_{roll_index:06d}",
        reason=candidate.reason,
        kind="attack",
        actor_id=character_sheet.id,
        target_id=target.id,
        stat=attack.id,
        modifier=attack.modifier,
        dc=dc,
        secret=False,
    )
