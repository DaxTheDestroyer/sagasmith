"""Rules Turn Resolution: resolve one player rules turn.

Consumes graph-state-shaped data and injected collaborators; produces state
updates plus skill names for the LangGraph Adapter to log. It performs no graph
activation logging and imports no LangGraph runtime objects.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
from sagasmith.schemas.mechanics import CharacterSheet, CombatState
from sagasmith.services.combat_engine import CombatEngine
from sagasmith.services.dice import DiceService
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


@dataclass(frozen=True)
class RulesTurnContext:
    """Everything resolve_rules_turn needs to resolve one player rules turn."""

    state: Mapping[str, Any]
    dice: DiceService
    cost: Any
    llm: Any | None = None
    provider_config: Any | None = None
    skill_store: Any | None = None


@dataclass(frozen=True)
class RulesTurnResult:
    """Result of resolve_rules_turn: graph-ready updates plus skill names."""

    state_updates: Mapping[str, Any]
    skills_activated: tuple[str, ...]


def resolve_rules_turn(context: RulesTurnContext) -> RulesTurnResult:
    """Resolve first-slice check/combat commands without LLM-authored math."""

    state = context.state
    raw_input = state.get("pending_player_input")
    if raw_input is None:
        return RulesTurnResult(state_updates={}, skills_activated=())
    normalized = " ".join(str(raw_input).strip().lower().split())

    rules_engine = RulesEngine(dice=context.dice)
    combat_engine = CombatEngine(dice=context.dice, rules=rules_engine)
    character_sheet = _character_sheet_from_state(state)
    check_results = list(state.get("check_results", []))
    pending_narration = list(state.get("pending_narration", []))
    skills_activated: list[str] = []

    try:
        if _LEGACY_PERCEPTION_TRIGGER_RE.match(normalized):
            _activate_skill(context, skills_activated, "skill-check-resolution")
            return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)

        if _looks_like_failed_mechanical_input(normalized):
            deterministic = deterministic_intents(
                normalized, scene_context=_scene_context_from_state(state)
            )
            if not deterministic:
                return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)

        candidates = _resolve_player_intent(raw_input, normalized, state, context)
        if not candidates or candidates[0].action == "none":
            if candidates and candidates[0].source == "budget_fallback":
                return _result(
                    _rules_error(check_results, "I didn't catch that — try `/check athletics 15`."),
                    skills_activated,
                )
            if _looks_like_failed_mechanical_input(normalized):
                return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)
            return RulesTurnResult(state_updates={}, skills_activated=tuple(skills_activated))

        primary = candidates[0]

        if primary.action == "skill_check":
            if primary.stat is None or primary.dc is None:
                return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)
            _activate_skill(context, skills_activated, "skill-check-resolution")
            check_result = rules_engine.resolve_check(
                character_sheet,
                stat=primary.stat,
                dc=primary.dc,
                reason=primary.reason,
                roll_index=len(check_results),
            )
            return _result(
                {"check_results": [*check_results, check_result.model_dump()]}, skills_activated
            )

        if primary.action == "start_combat":
            _activate_skill(context, skills_activated, "combat-resolution")
            combat_state, initiative_results = combat_engine.start_encounter(
                character_sheet,
                make_first_slice_enemies(),
                roll_index=len(check_results),
            )
            return _result(
                {
                    "combat_state": combat_state.model_dump(),
                    "check_results": [
                        *check_results,
                        *(result.model_dump() for result in initiative_results),
                    ],
                    "phase": "combat",
                },
                skills_activated,
            )

        if primary.action == "strike":
            _activate_skill(context, skills_activated, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            if primary.target_id is None or primary.attack_id is None:
                return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)
            updated_state, check_result, damage_roll = combat_engine.resolve_strike(
                combat_state,
                character_sheet.id,
                primary.target_id,
                primary.attack_id,
                roll_index=len(check_results),
            )
            if damage_roll is not None:
                pending_narration.append(f"Rules audit: damage_roll={damage_roll.roll_id}")
            return _result(
                _combat_update(
                    combat_engine,
                    updated_state,
                    [*check_results, check_result.model_dump()],
                    pending_narration,
                ),
                skills_activated,
            )

        if primary.action == "move":
            _activate_skill(context, skills_activated, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            if primary.position is None:
                return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)
            updated_state = combat_engine.move(combat_state, character_sheet.id, primary.position)  # type: ignore[arg-type]
            return _result(
                _combat_update(combat_engine, updated_state, check_results, pending_narration),
                skills_activated,
            )

        if primary.action == "end_turn":
            _activate_skill(context, skills_activated, "combat-resolution")
            combat_state = _combat_state_from_state(state)
            updated_state = combat_engine.end_turn(combat_state)
            return _result(
                _combat_update(combat_engine, updated_state, check_results, pending_narration),
                skills_activated,
            )

        return _result(_rules_error(check_results, _HELP_MESSAGE), skills_activated)
    except ValueError as exc:
        return _result(
            _rules_error(
                check_results,
                (
                    f"Rules error: {exc}. Try `roll athletics dc 15`, `start combat`, "
                    "or `strike enemy_weak_melee with longsword`."
                ),
            ),
            skills_activated,
        )


def _result(updates: Mapping[str, Any], skills_activated: list[str]) -> RulesTurnResult:
    return RulesTurnResult(state_updates=updates, skills_activated=tuple(skills_activated))


def _activate_skill(
    context: RulesTurnContext, skills_activated: list[str], skill_name: str
) -> None:
    store = context.skill_store
    if store is not None:
        try:
            load_skill(store, skill_name, agent_name="rules_lawyer")
        except (SkillNotFoundError, UnauthorizedSkillError):
            return
    if skill_name not in skills_activated:
        skills_activated.append(skill_name)


def _resolve_player_intent(
    raw_input: object, normalized: str, state: Mapping[str, Any], context: RulesTurnContext
) -> list[IntentCandidate]:
    scene_context = _scene_context_from_state(state)
    deterministic = deterministic_intents(normalized, scene_context=scene_context)
    if deterministic:
        return deterministic
    if context.llm is None:
        return []
    return resolve_intents(
        str(raw_input),
        scene_context=scene_context,
        llm_client=context.llm,
        cost_governor=context.cost,
        model=_get_default_model(context),
        cheap_model=_get_cheap_model(context),
        turn_id=state.get("turn_id") if isinstance(state.get("turn_id"), str) else None,
    )


def _get_default_model(context: RulesTurnContext) -> str:
    return getattr(context.provider_config, "default_model", "fake-default")


def _get_cheap_model(context: RulesTurnContext) -> str:
    return getattr(context.provider_config, "cheap_model", "fake-cheap")


def _scene_context_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    scene_context: dict[str, Any] = {"turn_id": state.get("turn_id")}
    scene_brief = state.get("scene_brief")
    if isinstance(scene_brief, dict):
        # Deterministic DC map may be provided by future scene-brief work; LLM DCs are ignored.
        if isinstance(scene_brief.get("skill_dcs"), dict):
            scene_context["skill_dcs"] = scene_brief["skill_dcs"]
        if isinstance(scene_brief.get("default_dc"), int):
            scene_context["default_dc"] = scene_brief["default_dc"]
    return scene_context


def _looks_like_failed_mechanical_input(normalized: str) -> bool:
    return normalized.startswith(
        ("roll ", "check ", "strike ", "move ", "start combat", "end turn", "perception")
    )


def _character_sheet_from_state(state: Mapping[str, Any]) -> CharacterSheet:
    sheet = state.get("character_sheet")
    if sheet is None:
        return make_first_slice_character()
    return CharacterSheet.model_validate(sheet)


def _combat_state_from_state(state: Mapping[str, Any]) -> CombatState:
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
