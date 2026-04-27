"""Oracle agent node.

Phase 6 replaces the stub with scene-brief-composition skill per
oracle-skills.md §2.3.
"""

from __future__ import annotations

from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.narrative import SceneBrief

_FIRST_SLICE_STUB_SCENE_BRIEF = SceneBrief(
    scene_id="scene_stub_001",
    intent="placeholder first-slice scene (replaced in Phase 6)",
    location=None,
    present_entities=[],
    beats=[],
    success_outs=[],
    failure_outs=[],
    pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
)


def oracle_node(state, services):
    """Populate scene_brief with a canned stub when absent."""
    if services._call_recorder is not None:
        services._call_recorder.append("oracle")
    activation = get_current_activation()
    if state["scene_brief"] is None:
        if activation is not None:
            store = services.skill_store
            if store is not None and store.find(name="scene-brief-composition", agent_scope="oracle") is not None:
                activation.set_skill("scene-brief-composition")
        return {"scene_brief": _FIRST_SLICE_STUB_SCENE_BRIEF.model_dump()}
    return {}
