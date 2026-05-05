"""Tests for the Scene Planning Module Interface.

All tests call plan_scene directly — no LangGraph or Textual plumbing.
Collaborators: real VaultService on tmp_path, :memory: sqlite, DeterministicFakeClient.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import sagasmith.vault.paths as vp
from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_campaign_seed,
    make_valid_memory_packet,
    make_valid_saga_state,
    make_valid_scene_brief,
    make_valid_world_bible,
)
from sagasmith.graph.bootstrap import default_skill_store
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.scene_planning import ScenePlanContext, plan_scene
from sagasmith.schemas.narrative import SceneBrief
from sagasmith.services.cost import CostGovernor
from sagasmith.services.errors import BudgetStopError
from sagasmith.vault import VaultService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VaultService:
    monkeypatch.setattr(vp, "DEFAULT_MASTER_OPTS", tmp_path / ".ttrpg" / "vault")
    return VaultService("cmp_001", tmp_path / "player_vault")


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    apply_migrations(c)
    return c


def _play_state(**overrides: Any) -> dict[str, Any]:
    """Minimal play-turn state: phase=play, no scene_brief, memory_packet and
    campaign context pre-loaded so campaign-context generation is skipped by default."""
    state = make_valid_saga_state().model_dump()
    state["phase"] = "play"
    state["scene_brief"] = None
    state["memory_packet"] = make_valid_memory_packet().model_dump()
    state["world_bible"] = make_valid_world_bible().model_dump()
    state["campaign_seed"] = make_valid_campaign_seed().model_dump()
    state.update(overrides)
    return state


def _ctx(
    *,
    state: dict[str, Any] | None = None,
    llm: Any = None,
    cost: Any = None,
    safety: Any = None,
    skill_store: Any = None,
    transcript_conn: Any = None,
    vault_service: Any = None,
    provider_config: Any = None,
) -> ScenePlanContext:
    """Factory for a baseline ScenePlanContext with no LLM and no skill_store."""
    return ScenePlanContext(
        state=state if state is not None else _play_state(),
        llm=llm,
        cost=cost if cost is not None else CostGovernor(session_budget_usd=1.0),
        safety=safety,
        skill_store=skill_store,
        transcript_conn=transcript_conn,
        vault_service=vault_service,
        provider_config=provider_config,
    )


def _scene_brief_client() -> DeterministicFakeClient:
    payload = make_valid_scene_brief(intent="The river investigation begins.").model_dump()
    return DeterministicFakeClient(
        scripted_responses={
            "oracle.scene-brief-composition": make_fake_llm_response(parsed_json=payload)
        }
    )


# ---------------------------------------------------------------------------
# 1. Fallback: no scene_brief, llm=None → deterministic fallback SceneBrief
# ---------------------------------------------------------------------------


def test_fallback_scene_brief_when_no_llm() -> None:
    plan = plan_scene(_ctx())

    assert "scene_brief" in plan.state_updates
    brief = SceneBrief.model_validate(plan.state_updates["scene_brief"])
    assert brief.scene_id == "scene_first_slice_001"
    assert plan.interrupt is None
    assert plan.pre_gate_events == ()


# ---------------------------------------------------------------------------
# 2. LLM path: llm set → LLM-generated SceneBrief returned
# ---------------------------------------------------------------------------


def test_replan_with_llm_returns_llm_scene_brief() -> None:
    plan = plan_scene(_ctx(llm=_scene_brief_client()))

    assert "scene_brief" in plan.state_updates
    brief = SceneBrief.model_validate(plan.state_updates["scene_brief"])
    assert brief.intent == "The river investigation begins."
    assert plan.interrupt is None


# ---------------------------------------------------------------------------
# 3. Bypass detection: player input triggers bypass → replan occurs, flag reset
# ---------------------------------------------------------------------------


def test_bypass_detection_triggers_replan() -> None:
    # With a scene_brief already present and beats unresolved, replan would
    # normally be skipped. Bypass input forces a replan despite that.
    state = _play_state(
        scene_brief=make_valid_scene_brief().model_dump(),
        resolved_beat_ids=[],  # beats not exhausted — no normal replan trigger
        oracle_bypass_detected=False,
        pending_player_input="I want to bypass the whole investigation",
    )
    plan = plan_scene(_ctx(state=state))

    # A new scene_brief is produced (replan triggered by bypass)
    assert "scene_brief" in plan.state_updates
    # oracle_bypass_detected is reset to False after successful replan
    assert plan.state_updates.get("oracle_bypass_detected") is False


# ---------------------------------------------------------------------------
# 4. Safety block: hard-limit intent → interrupt, no scene_brief in updates
# ---------------------------------------------------------------------------


def test_safety_block_returns_interrupt_and_no_scene_brief() -> None:
    # "graphic_sexual_content" is an exact hard-limit term → Blocked
    state = _play_state(pending_player_input="graphic_sexual_content")
    plan = plan_scene(_ctx(state=state))

    assert plan.interrupt is not None
    assert plan.interrupt.kind == "safety_block"
    assert "scene_brief" not in plan.state_updates
    assert len(plan.pre_gate_events) == 1
    assert plan.pre_gate_events[0].kind == "pre_gate_block"


# ---------------------------------------------------------------------------
# 5. Safety reroute: soft-limit intent → pre_gate_events populated, plan continues
# ---------------------------------------------------------------------------


def test_safety_reroute_appends_event_and_continues() -> None:
    # "graphic violence" matches the soft limit graphic_violence
    state = _play_state(pending_player_input="I want to include graphic violence in the scene")
    plan = plan_scene(_ctx(state=state))

    assert plan.interrupt is None
    assert len(plan.pre_gate_events) == 1
    assert plan.pre_gate_events[0].kind == "pre_gate_reroute"
    assert "scene_brief" in plan.state_updates


# ---------------------------------------------------------------------------
# 6. Budget stop: compose_scene_brief raises BudgetStopError → interrupt
# ---------------------------------------------------------------------------


def test_budget_stop_returns_interrupt() -> None:
    with patch(
        "sagasmith.scene_planning.builder.compose_scene_brief",
        side_effect=BudgetStopError("budget exhausted"),
    ):
        plan = plan_scene(_ctx(llm=_scene_brief_client()))

    assert plan.interrupt is not None
    assert plan.interrupt.kind == "budget_stop"
    assert "budget exhausted" in plan.interrupt.reason
    assert "scene_brief" not in plan.state_updates


# ---------------------------------------------------------------------------
# 7. Campaign context gating: world_bible absent → generated, skills recorded
# ---------------------------------------------------------------------------


def test_campaign_context_generated_when_missing(vault: VaultService) -> None:
    wb_payload = make_valid_world_bible().model_dump()
    cs_payload = make_valid_campaign_seed().model_dump()
    sb_payload = make_valid_scene_brief(intent="First river scene.").model_dump()
    client = DeterministicFakeClient(
        scripted_responses={
            "oracle.world-bible-generation": make_fake_llm_response(parsed_json=wb_payload),
            "oracle.campaign-seed-generation": make_fake_llm_response(parsed_json=cs_payload),
            "oracle.scene-brief-composition": make_fake_llm_response(parsed_json=sb_payload),
        }
    )
    state = _play_state(world_bible=None, campaign_seed=None)
    store = default_skill_store()
    plan = plan_scene(
        ScenePlanContext(
            state=state,
            llm=client,
            cost=CostGovernor(session_budget_usd=5.0),
            safety=None,
            skill_store=store,
            transcript_conn=None,
            vault_service=vault,
            provider_config=None,
        )
    )

    assert "world_bible" in plan.state_updates
    assert "campaign_seed" in plan.state_updates
    assert "world-bible-generation" in plan.skills_activated
    assert "campaign-seed-generation" in plan.skills_activated


# ---------------------------------------------------------------------------
# 8. Campaign context skipped: world_bible already present → gen skills absent
# ---------------------------------------------------------------------------


def test_campaign_context_skipped_when_already_present() -> None:
    state = _play_state(
        world_bible=make_valid_world_bible().model_dump(),
        campaign_seed=make_valid_campaign_seed().model_dump(),
    )
    store = default_skill_store()
    plan = plan_scene(
        ScenePlanContext(
            state=state,
            llm=_scene_brief_client(),
            cost=CostGovernor(session_budget_usd=1.0),
            safety=None,
            skill_store=store,
            transcript_conn=None,
            vault_service=None,
            provider_config=None,
        )
    )

    assert "world_bible" not in plan.state_updates
    assert "campaign_seed" not in plan.state_updates
    assert "world-bible-generation" not in plan.skills_activated
    assert "campaign-seed-generation" not in plan.skills_activated


# ---------------------------------------------------------------------------
# 9. skill_store=None → skills_activated is empty
# ---------------------------------------------------------------------------


def test_no_skill_store_produces_empty_skills_activated() -> None:
    plan = plan_scene(_ctx(skill_store=None))

    assert plan.skills_activated == ()


# ---------------------------------------------------------------------------
# 10. No replan: scene_brief present, beats unresolved → state_updates is empty
# ---------------------------------------------------------------------------


def test_no_replan_when_scene_brief_has_unresolved_beats() -> None:
    state = _play_state(
        scene_brief=make_valid_scene_brief().model_dump(),
        resolved_beat_ids=[],
        oracle_bypass_detected=False,
    )
    plan = plan_scene(_ctx(state=state))

    assert "scene_brief" not in plan.state_updates
    assert plan.interrupt is None
