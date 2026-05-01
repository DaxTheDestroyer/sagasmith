"""Rules Lawyer agent node for deterministic first-slice mechanics."""

from __future__ import annotations

import re
from typing import Any

from sagasmith.agents.rules_lawyer.intent_to_proposal import proposals_from_candidates
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.mechanics import CharacterSheet, CombatState
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.intent_resolution import (
    IntentCandidate,
    deterministic_intents,
    resolve_intents,
)
from sagasmith.services.rules_engine import RulesEngine
from sagasmith.skills_adapter import load_skill
from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError

_LEGACY_PERCEPTION_TRIGGER_RE = re.compile(r"^roll\s+perception$")

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
        if _LEGACY_PERCEPTION_TRIGGER_RE.match(normalized):
            _activate_skill(services, "skill-check-resolution")
            return _rules_error(check_results, _HELP_MESSAGE)

        if _looks_like_failed_mechanical_input(normalized):
            deterministic = deterministic_intents(
                normalized, scene_context=_scene_context_from_state(state)
            )
            if not deterministic:
                return _rules_error(check_results, _HELP_MESSAGE)

        candidates = _resolve_player_intent(raw_input, normalized, state, services)
        if not candidates or candidates[0].action == "none":
            if candidates and candidates[0].source == "budget_fallback":
                return _rules_error(
                    check_results, "I didn't catch that — try `/check athletics 15`."
                )
            if _looks_like_failed_mechanical_input(normalized):
                return _rules_error(check_results, _HELP_MESSAGE)
            return {}

        primary = candidates[0]

        if primary.action == "skill_check":
            if primary.stat is None or primary.dc is None:
                return _rules_error(check_results, _HELP_MESSAGE)
            _activate_skill(services, "skill-check-resolution")
            proposals_from_candidates(
                [primary],
                character_sheet=character_sheet,
                rules_engine=rules_engine,
                combat_engine=combat_engine,
                combat_state=None,
                roll_index=len(check_results),
            )
            check_result = rules_engine.resolve_check(
                character_sheet,
                stat=primary.stat,
                dc=primary.dc,
                reason=primary.reason,
                roll_index=len(check_results),
            )
            return {"check_results": [*check_results, check_result.model_dump()]}

        if primary.action == "start_combat":
            _activate_skill(services, "combat-resolution")
            combat_state, initiative_results = combat_engine.start_encounter(
                character_sheet,
                make_first_slice_enemies(),
                roll_index=len(check_results),
            )
            return {
                "combat_state": combat_state.model_dump(),
                "check_results": [
                    *check_results,
                    *(result.model_dump() for result in initiative_results),
                ],
                "phase": "combat",
            }

        if primary.action == "strike":
            _activate_skill(services, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            if primary.target_id is None or primary.attack_id is None:
                return _rules_error(check_results, _HELP_MESSAGE)
            proposals_from_candidates(
                [primary],
                character_sheet=character_sheet,
                rules_engine=rules_engine,
                combat_engine=combat_engine,
                combat_state=combat_state,
                roll_index=len(check_results),
            )
            updated_state, check_result, damage_roll = combat_engine.resolve_strike(
                combat_state,
                character_sheet.id,
                primary.target_id,
                primary.attack_id,
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

        if primary.action == "move":
            _activate_skill(services, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            if primary.position is None:
                return _rules_error(check_results, _HELP_MESSAGE)
            updated_state = combat_engine.move(combat_state, character_sheet.id, primary.position)  # type: ignore[arg-type]
            return _combat_update(combat_engine, updated_state, check_results, pending_narration)

        if primary.action == "end_turn":
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


def _resolve_player_intent(
    raw_input: str, normalized: str, state: dict[str, Any], services: Any
) -> list[IntentCandidate]:
    scene_context = _scene_context_from_state(state)
    deterministic = deterministic_intents(normalized, scene_context=scene_context)
    if deterministic:
        return deterministic
    llm_client = getattr(services, "llm", None)
    if llm_client is None:
        return []
    return resolve_intents(
        raw_input,
        scene_context=scene_context,
        llm_client=llm_client,
        cost_governor=getattr(services, "cost", None),
        model=_get_default_model(services),
        cheap_model=_get_cheap_model(services),
        turn_id=state.get("turn_id") if isinstance(state.get("turn_id"), str) else None,
    )


def _get_default_model(services: Any) -> str:
    config = getattr(services, "provider_config", None)
    return getattr(config, "default_model", "fake-default")


def _get_cheap_model(services: Any) -> str:
    config = getattr(services, "provider_config", None)
    return getattr(config, "cheap_model", "fake-cheap")


def _scene_context_from_state(state: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {"turn_id": state.get("turn_id")}
    scene_brief = state.get("scene_brief")
    if isinstance(scene_brief, dict):
        # Deterministic DC map may be provided by future scene-brief work; LLM DCs are ignored.
        if isinstance(scene_brief.get("skill_dcs"), dict):
            context["skill_dcs"] = scene_brief["skill_dcs"]
        if isinstance(scene_brief.get("default_dc"), int):
            context["default_dc"] = scene_brief["default_dc"]
    return context


def _looks_like_failed_mechanical_input(normalized: str) -> bool:
    return normalized.startswith(
        ("roll ", "check ", "strike ", "move ", "start combat", "end turn", "perception")
    )


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
        result["pending_narration"] = [
            *pending_narration,
            "Combat complete; returning to exploration.",
        ]
    return result


def _rules_error(check_results: list[object], message: str) -> dict[str, Any]:
    return {"check_results": check_results, "pending_narration": [message]}
