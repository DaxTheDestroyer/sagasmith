"""Tests for RulesLawyer intent-to-proposal conversion."""

from __future__ import annotations

from sagasmith.agents.rules_lawyer.intent_to_proposal import (
    intents_to_proposals,
    proposals_from_candidates,
)
from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.mechanics import CheckProposal
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.dice import DiceService
from sagasmith.services.intent_resolution import IntentCandidate
from sagasmith.services.rules_engine import RulesEngine


def _engines() -> tuple[RulesEngine, CombatEngine]:
    rules = RulesEngine(dice=DiceService(campaign_seed="intent", session_seed="proposal"))
    return rules, CombatEngine(dice=rules.dice, rules=rules)


def test_skill_intent_converts_to_schema_valid_proposal_with_sheet_modifier() -> None:
    sheet = make_first_slice_character()
    rules, combat = _engines()
    proposals = intents_to_proposals(
        "roll athletics dc 15",
        scene_context=None,
        character_sheet=sheet,
        rules_engine=rules,
        combat_engine=combat,
        roll_index=2,
    )

    assert len(proposals) == 1
    proposal = CheckProposal.model_validate(proposals[0].model_dump())
    assert proposal.id == "check_athletics_000002"
    assert proposal.kind == "skill"
    assert proposal.actor_id == sheet.id
    assert proposal.modifier == sheet.skills["athletics"]
    assert proposal.dc == 15


def test_combat_strike_intent_converts_to_attack_proposal_with_target_ac() -> None:
    sheet = make_first_slice_character()
    rules, combat = _engines()
    combat_state, _ = combat.start_encounter(sheet, make_first_slice_enemies())

    proposals = proposals_from_candidates(
        [
            IntentCandidate(
                action="strike",
                confidence=0.9,
                reason="strike classified",
                source="deterministic",
                target_id="enemy_weak_melee",
                attack_id="longsword",
            )
        ],
        character_sheet=sheet,
        rules_engine=rules,
        combat_engine=combat,
        combat_state=combat_state,
        roll_index=4,
    )

    proposal = CheckProposal.model_validate(proposals[0].model_dump())
    target = next(item for item in combat_state.combatants if item.id == "enemy_weak_melee")
    assert proposal.kind == "attack"
    assert proposal.id == "check_attack_longsword_000004"
    assert proposal.modifier == sheet.attacks[0].modifier
    assert proposal.dc == target.armor_class
    assert proposal.target_id == target.id


def test_invalid_intents_do_not_generate_proposals() -> None:
    sheet = make_first_slice_character()
    rules, combat = _engines()

    proposals = proposals_from_candidates(
        [IntentCandidate(action="none", confidence=1.0, reason="narrative", source="deterministic")],
        character_sheet=sheet,
        rules_engine=rules,
        combat_engine=combat,
    )

    assert proposals == []
