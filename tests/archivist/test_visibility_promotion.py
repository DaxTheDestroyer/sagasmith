"""Tests for Archivist visibility-promotion skill."""

from __future__ import annotations

from sagasmith.agents.archivist.skills.visibility_promotion.logic import promote_visibility
from sagasmith.vault.page import NpcFrontmatter, VaultPage


def _npc_page(*, visibility: str = "gm_only") -> VaultPage:
    return VaultPage(
        NpcFrontmatter(
            id="npc_marcus_innkeeper",
            type="npc",
            name="Marcus the Innkeeper",
            aliases=["Marcus"],
            visibility=visibility,  # type: ignore[arg-type]
            first_encountered="1",
            species="human",
            role="innkeeper",
            status="alive",
            disposition_to_pc="neutral",
        ),
        "Marcus runs the Bent Copper.",
    )


def test_present_entity_promotes_to_player_known() -> None:
    page = _npc_page(visibility="gm_only")

    visibility = promote_visibility(
        page,
        {"scene_brief": {"present_entities": ["npc_marcus_innkeeper"]}},
    )

    assert visibility == "player_known"


def test_name_mention_only_foreshadows_gm_only_page() -> None:
    page = _npc_page(visibility="gm_only")

    visibility = promote_visibility(
        page,
        {"recent_narration_lines": ["A sailor whispers that Marcus knows the river signs."]},
    )

    assert visibility == "foreshadowed"


def test_name_mention_does_not_jump_to_player_known() -> None:
    page = _npc_page(visibility="gm_only")

    visibility = promote_visibility(page, {"player_input": "I ask about Marcus."})

    assert visibility == "foreshadowed"


def test_existing_visibility_is_not_demoted() -> None:
    page = _npc_page(visibility="player_known")

    visibility = promote_visibility(page, {"recent_narration_lines": ["No mention here."]})

    assert visibility == "player_known"
