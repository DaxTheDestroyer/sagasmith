"""Unit tests for Orator scene rendering pipeline (06-04)."""

from __future__ import annotations

from sagasmith.agents.orator.dice_ux import prepare_dice_ux
from sagasmith.agents.orator.skills.scene_rendering.logic import (
    RenderResult,
    _detect_resolved_beats,
    render_scene,
)
from sagasmith.evals.fixtures import (
    make_valid_content_policy,
    make_valid_memory_packet,
    make_valid_player_profile,
    make_valid_scene_brief,
)
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.schemas.mechanics import CheckResult, RollResult
from sagasmith.schemas.provider import (
    CompletedEvent,
    LLMResponse,
    TokenEvent,
    TokenUsage,
)

# ---------------------------------------------------------------------------
# Dice UX mode tests
# ---------------------------------------------------------------------------


class TestDiceUX:
    def test_auto_mode_weaves_outcomes(self) -> None:
        ctx = prepare_dice_ux("auto", [])
        assert ctx.mode == "auto"
        assert "naturally" in ctx.prompt_instruction.lower() or "vivid" in ctx.prompt_instruction.lower()

    def test_reveal_mode_shows_dice_details(self) -> None:
        ctx = prepare_dice_ux("reveal", [])
        assert ctx.mode == "reveal"
        assert "dice" in ctx.prompt_instruction.lower() or "roll" in ctx.prompt_instruction.lower()

    def test_hidden_mode_never_names_rolls(self) -> None:
        ctx = prepare_dice_ux("hidden", [])
        assert ctx.mode == "hidden"
        assert "never" in ctx.prompt_instruction.lower()

    def test_check_results_encoded_as_constraints(self) -> None:
        cr = CheckResult(
            proposal_id="check_perception_turn_001",
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
        ctx = prepare_dice_ux("auto", [cr])
        assert len(ctx.constraint_payload) == 1
        assert ctx.constraint_payload[0]["degree"] == "success"


# ---------------------------------------------------------------------------
# Scene rendering pipeline tests
# ---------------------------------------------------------------------------


class TestRenderScene:
    def test_no_llm_client_returns_fallback(self) -> None:
        """Without LLM client, returns deterministic fallback."""
        result = render_scene(
            scene_brief=make_valid_scene_brief(),
            check_results=[],
            memory_packet=make_valid_memory_packet(),
            content_policy=make_valid_content_policy(),
            player_profile=make_valid_player_profile(),
            house_rules_dice_ux=None,
            llm_client=None,
            narration_model="fake",
            cheap_model="fake-cheap",
            cost_governor=None,
        )
        assert result.used_fallback is True
        assert result.narration_lines == ["The scene shifts. A new detail draws your attention."]

    def test_happy_path_with_fake_stream(self) -> None:
        """With a fake streaming client, narration passes all gates."""
        narration_text = "You stand at the riverbank, the morning mist curling over the water."
        client = DeterministicFakeClient(
            scripted_streams={
                "orator.scene-rendering": [
                    TokenEvent(kind="token", text=narration_text),
                    CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text=narration_text,
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
        assert result.used_fallback is False
        assert narration_text in result.narration_lines[0]

    def test_hard_limit_inline_matcher_cancels_stream(self) -> None:
        """Inline hard-limit matcher cancels the stream on hit."""
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
        # Should use fallback after inline matcher hit
        assert result.used_fallback is True
        assert len(result.safety_events) > 0

    def test_post_gate_rewrite_triggers_rewrite(self) -> None:
        """Post-gate rewrite triggers a rewrite attempt."""
        # First stream has a soft-limit violation, second is clean
        narration_bad = "Gore covers the floor in the dimly lit room."
        client = DeterministicFakeClient(
            scripted_streams={
                "orator.scene-rendering": [
                    TokenEvent(kind="token", text=narration_bad),
                    CompletedEvent(
                        kind="completed",
                        response=LLMResponse(
                            text=narration_bad,
                            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                            finish_reason="stop",
                        ),
                    ),
                ],
            },
        )
        # With no LLM client for the post-gate classifier, it uses inline scan
        # "gore" triggers a soft-limit rewrite
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
        # Should have safety events from the rewrite attempts
        assert len(result.safety_events) > 0

    def test_resolved_beats_detected(self) -> None:
        """Resolved beat IDs are detected from narration content."""
        brief = make_valid_scene_brief()
        narration = "You investigate the riverbank clues near the old ford."
        result = _detect_resolved_beats(narration, brief)
        assert isinstance(result, list)
        # Should detect at least one beat since narration is substantial
        assert len(result) >= 1

    def test_empty_brief_beats_returns_empty(self) -> None:
        """Empty beat_ids returns empty resolved list."""
        from sagasmith.schemas.narrative import SceneBrief

        brief = SceneBrief(
            scene_id="s1",
            intent="test",
            location=None,
            present_entities=[],
            beats=[],
            beat_ids=[],
            success_outs=[],
            failure_outs=[],
            pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        )
        result = _detect_resolved_beats("Some narration.", brief)
        assert result == []


# ---------------------------------------------------------------------------
# RenderResult tests
# ---------------------------------------------------------------------------


class TestRenderResult:
    def test_fallback_result_shape(self) -> None:
        result = RenderResult(
            narration_lines=["fallback"],
            resolved_beat_ids=[],
            safety_events=[],
            used_fallback=True,
        )
        assert result.used_fallback is True
        assert result.narration_lines == ["fallback"]
