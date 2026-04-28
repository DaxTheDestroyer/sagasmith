"""Rules Lawyer agent node for deterministic first-slice mechanics."""

from __future__ import annotations

import re
from typing import Any

from sagasmith.graph.activation_log import get_current_activation
from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.mechanics import CharacterSheet, CombatState
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.rules_engine import RulesEngine
from sagasmith.skills_adapter import load_skill
from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError

_STAT_PATTERN = r"(athletics|acrobatics|survival|intimidation|perception)"
_ROLL_CHECK_RE = re.compile(rf"^(?:roll|check)\s+{_STAT_PATTERN}\s+dc\s+(\d+)$")
_PERCEPTION_RE = re.compile(r"^perception\s+dc\s+(\d+)$")
_START_COMBAT_RE = re.compile(r"^start\s+combat$")
_STRIKE_RE = re.compile(r"^strike\s+(enemy_weak_melee|enemy_weak_ranged)\s+with\s+(longsword|shortbow)$")
_MOVE_RE = re.compile(r"^move\s+(close|near|far|behind_cover)$")
_END_TURN_RE = re.compile(r"^end\s+turn$")

_HELP_MESSAGE = (
    "Rules error: Unsupported first-slice action. Try `roll athletics dc 15`, "
    "`start combat`, or `strike enemy_weak_melee with longsword`."
)


def rules_lawyer_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Resolve first-slice check/combat commands without LLM-authored math."""
    if services._call_recorder is not None:
        services._call_recorder.append("rules_lawyer")
    raw_input = state.get("pending_player_input")
    if raw_input is None:
        return {}
    normalized = " ".join(raw_input.strip().lower().split())

    rules_engine = RulesEngine(dice=services.dice)
    combat_engine = CombatEngine(dice=services.dice, rules=rules_engine)
    character_sheet = _character_sheet_from_state(state)
    check_results = list(state.get("check_results", []))
    pending_narration = list(state.get("pending_narration", []))

    try:
        if match := _ROLL_CHECK_RE.match(normalized):
            stat = match.group(1)
            dc = int(match.group(2))
            _activate_skill(services, "skill-check-resolution")
            check_result = rules_engine.resolve_check(
                character_sheet,
                stat=stat,
                dc=dc,
                reason=f"player requested {stat} check",
                roll_index=len(check_results),
            )
            return {"check_results": [*check_results, check_result.model_dump()]}

        if match := _PERCEPTION_RE.match(normalized):
            dc = int(match.group(1))
            _activate_skill(services, "skill-check-resolution")
            check_result = rules_engine.resolve_check(
                character_sheet,
                stat="perception",
                dc=dc,
                reason="player requested perception check",
                roll_index=len(check_results),
            )
            return {"check_results": [*check_results, check_result.model_dump()]}

        if _START_COMBAT_RE.match(normalized):
            _activate_skill(services, "combat-resolution")
            combat_state, initiative_results = combat_engine.start_encounter(
                character_sheet,
                make_first_slice_enemies(),
                roll_index=len(check_results),
            )
            return {
                "combat_state": combat_state.model_dump(),
                "check_results": [*check_results, *(result.model_dump() for result in initiative_results)],
                "phase": "combat",
            }

        if match := _STRIKE_RE.match(normalized):
            _activate_skill(services, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            target_id = match.group(1)
            attack_id = match.group(2)
            updated_state, check_result, damage_roll = combat_engine.resolve_strike(
                combat_state,
                character_sheet.id,
                target_id,
                attack_id,
                roll_index=len(check_results),
            )
            if damage_roll is not None:
                pending_narration.append(f"Rules audit: damage_roll={damage_roll.roll_id}")
            return _combat_update(
                combat_engine,
                updated_state,
                [*check_results, check_result.model_dump()],
                pending_narration,
            )

        if match := _MOVE_RE.match(normalized):
            _activate_skill(services, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            updated_state = combat_engine.move(combat_state, character_sheet.id, match.group(1))
            return _combat_update(combat_engine, updated_state, check_results, pending_narration)

        if _END_TURN_RE.match(normalized):
            _activate_skill(services, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            updated_state = combat_engine.end_turn(combat_state)
            return _combat_update(combat_engine, updated_state, check_results, pending_narration)

        return _rules_error(check_results, _HELP_MESSAGE)
    except ValueError as exc:
        return _rules_error(
            check_results,
            (
                f"Rules error: {exc}. Try `roll athletics dc 15`, `start combat`, "
                "or `strike enemy_weak_melee with longsword`."
            ),
        )


def _activate_skill(services: Any, skill_name: str) -> None:
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None:
            try:
                load_skill(store, skill_name, agent_name="rules_lawyer")
                activation.set_skill(skill_name)
            except (SkillNotFoundError, UnauthorizedSkillError):
                # Unit tests may run with an empty store; fall through to unskilled path
                pass


def _character_sheet_from_state(state: dict[str, Any]) -> CharacterSheet:
    sheet = state.get("character_sheet")
    if sheet is None:
        return make_first_slice_character()
    return CharacterSheet.model_validate(sheet)


def _combat_state_from_state(state: dict[str, Any]) -> CombatState:
    combat_state = state.get("combat_state")
    if combat_state is None:
        raise ValueError("combat has not started")
    return CombatState.model_validate(combat_state)


def _combat_update(
    combat_engine: CombatEngine,
    combat_state: CombatState,
    check_results: list[object],
    pending_narration: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "combat_state": combat_state.model_dump(),
        "check_results": check_results,
    }
    if pending_narration:
        result["pending_narration"] = pending_narration
    if combat_engine.is_encounter_complete(combat_state):
        result["phase"] = "play"
        result["pending_narration"] = [*pending_narration, "Combat complete; returning to exploration."]
    return result


def _rules_error(check_results: list[object], message: str) -> dict[str, Any]:
    return {"check_results": check_results, "pending_narration": [message]}
