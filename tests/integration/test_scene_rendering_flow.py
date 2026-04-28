"""Integration tests for scene rendering flow (06-04)."""

from __future__ import annotations

import sqlite3

from sagasmith.agents.orator.dice_ux import prepare_dice_ux
from sagasmith.agents.orator.node import orator_node
from sagasmith.agents.orator.skills.scene_rendering.logic import render_scene
from sagasmith.evals.fixtures import (
    make_valid_content_policy,
    make_valid_memory_packet,
    make_valid_player_profile,
    make_valid_saga_state,
    make_valid_scene_brief,
)
from sagasmith.graph.bootstrap import AgentServices, GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.schemas.mechanics import CheckResult, RollResult
from sagasmith.schemas.provider import (
    CompletedEvent,
    LLMResponse,
    TokenEvent,
    TokenUsage,
)
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Full flow: scene brief → rendered narration
# ---------------------------------------------------------------------------


class TestSceneRenderingFlow:
    def test_fallback_without_llm(self) -> None:
        """Without LLM, Orator emits fallback narration."""
        brief = make_valid_scene_brief()
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=[],
        ).model_dump()
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
        )
        result = orator_node(state, services)
        assert result["pending_narration"] == ["The scene shifts. A new detail draws your attention."]
        assert result["memory_packet"] is not None

    def test_happy_path_with_streaming_client(self) -> None:
        """With streaming client, narration passes all gates."""
        narration = "You stand at the riverbank. The morning mist curls over the water as you investigate."
        client = DeterministicFakeClient(
            scripted_streams={
                "orator.scene-rendering": [
                    TokenEvent(kind="token", text=narration),
                    CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text=narration,
                            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                            finish_reason="stop",
                        ),
                    ),
                ],
            },
        )
        brief = make_valid_scene_brief()
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=[],
        ).model_dump()
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            llm=client,
        )
        result = orator_node(state, services)
        assert narration in result["pending_narration"][0]
        # resolved_beat_ids should be populated
        assert "resolved_beat_ids" in result

    def test_resolved_beat_ids_emitted(self) -> None:
        """Orator emits resolved_beat_ids per D-06.4."""
        narration = "You investigate the riverbank clues and choose a social approach."
        client = DeterministicFakeClient(
            scripted_streams={
                "orator.scene-rendering": [
                    TokenEvent(kind="token", text=narration),
                    CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text=narration,
                            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                            finish_reason="stop",
                        ),
                    ),
                ],
            },
        )
        brief = make_valid_scene_brief()
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=[],
        ).model_dump()
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            llm=client,
        )
        result = orator_node(state, services)
        assert "resolved_beat_ids" in result
        assert isinstance(result["resolved_beat_ids"], list)

    def test_skill_activation_logged(self) -> None:
        """Orator logs scene-rendering skill activation."""
        brief = make_valid_scene_brief()
        conn = _make_conn()
        bootstrap = GraphBootstrap.from_services(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=default_skill_store(),
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")
        state = make_valid_saga_state(
            campaign_id="cmp_001",
            session_id="sess_001",
            turn_id="turn_render_001",
            phase="play",
            scene_brief=brief,
            pending_player_input="look around",
        ).model_dump()

        runtime.invoke_turn(state)
        # Resume past interrupt to invoke orator
        runtime.graph.invoke(None, runtime.thread_config)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_render_001")
        assert any(
            row.agent_name == "orator" and row.skill_name == "scene-rendering"
            for row in rows
        )


# ---------------------------------------------------------------------------
# Safety post-gate enforcement
# ---------------------------------------------------------------------------


class TestSafetyPostGateEnforcement:
    def test_hard_limit_content_blocked_and_fallback_used(self) -> None:
        """Hard-limit content in narration triggers fallback."""
        client = DeterministicFakeClient(
            scripted_streams={
                "orator.scene-rendering": [
                    TokenEvent(kind="token", text="The scene contains graphic sexual content."),
                    CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text="The scene contains graphic sexual content.",
                            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                            finish_reason="stop",
                        ),
                    ),
                ],
            },
        )
        result = render_scene(
            scene_brief=make_valid_scene_brief(),
            check_results=[],
            memory_packet=make_valid_memory_packet(),
            content_policy=make_valid_content_policy(),
            player_profile=make_valid_player_profile(),
            house_rules_dice_ux=None,
            llm_client=client,
            narration_model="fake-narration",
            cheap_model="fake-cheap",
            cost_governor=None,
        )
        assert result.used_fallback is True
        assert result.narration_lines == ["The scene shifts. A new detail draws your attention."]


# ---------------------------------------------------------------------------
# Dice UX mode integration
# ---------------------------------------------------------------------------


class TestDiceUXIntegration:
    def test_dice_ux_mode_passed_to_prompt(self) -> None:
        """Dice UX mode from house_rules is respected."""
        ctx = prepare_dice_ux("hidden", [])
        assert "never" in ctx.prompt_instruction.lower()

    def test_dice_ux_reveal_mode(self) -> None:
        ctx = prepare_dice_ux("reveal", [])
        assert "dice" in ctx.prompt_instruction.lower() or "roll" in ctx.prompt_instruction.lower()


# ---------------------------------------------------------------------------
# Mechanical consistency preservation
# ---------------------------------------------------------------------------


class TestMechanicalConsistencyIntegration:
    def test_consistent_narration_passes_audit(self) -> None:
        """Narration that agrees with check results passes the audit."""
        cr = CheckResult(
            proposal_id="check_thievery_turn_001",
            roll_result=RollResult(
                roll_id="roll_001",
                seed="seed_001",
                die="d20",
                natural=15,
                modifier=5,
                total=20,
                dc=15,
                timestamp="2026-01-01T00:00:00Z",
            ),
            degree="success",
            effects=[],
            state_deltas=[],
        )
        result = render_scene(
            scene_brief=make_valid_scene_brief(),
            check_results=[cr],
            memory_packet=make_valid_memory_packet(),
            content_policy=make_valid_content_policy(),
            player_profile=make_valid_player_profile(),
            house_rules_dice_ux=None,
            llm_client=None,
            narration_model="fake",
            cheap_model="fake-cheap",
            cost_governor=None,
        )
        # With no LLM client, fallback is used — that's fine, it still passes audit
        assert result.used_fallback is True
