"""Rules Lawyer agent node.

Phase 5 replaces trigger-phrase parser with IntentResolver +
skill-check-resolution skill per rules-lawyer-skills.md §2.3.
"""

from __future__ import annotations

from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.mechanics import CheckResult
from sagasmith.services.pf2e import compute_degree
from sagasmith.skills_adapter import load_skill
from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError

_TRIGGER_PHRASES = {"roll perception", "roll d20"}


def rules_lawyer_node(state, services):
    """Deterministic trigger-phrase → DiceService → CheckResult."""
    if services._call_recorder is not None:
        services._call_recorder.append("rules_lawyer")
    raw_input = state.get("pending_player_input")
    if raw_input is None:
        return {}
    normalized = raw_input.strip().lower()
    if normalized not in _TRIGGER_PHRASES:
        return {}

    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None:
            try:
                load_skill(store, "skill-check-resolution", agent_name="rules_lawyer")
                activation.set_skill("skill-check-resolution")
            except (SkillNotFoundError, UnauthorizedSkillError):
                # Unit tests may run with an empty store; fall through to unskilled path
                pass

    character_sheet = state.get("character_sheet")
    actor_id = character_sheet["id"] if character_sheet is not None else "player"
    roll_index = len(state["check_results"])
    roll = services.dice.roll_d20(
        purpose="perception",
        actor_id=actor_id,
        modifier=0,
        roll_index=roll_index,
    )
    check_result = CheckResult(
        proposal_id=f"cp_{roll.roll_id}",
        roll_result=roll,
        degree=compute_degree(natural=roll.natural, total=roll.total, dc=10),
        effects=[],
        state_deltas=[],
    )
    return {"check_results": state["check_results"] + [check_result.model_dump()]}
