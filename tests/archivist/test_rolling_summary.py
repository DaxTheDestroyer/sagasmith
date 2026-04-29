"""Tests for rolling-summary-update skill."""

from __future__ import annotations

from sagasmith.agents.archivist.skills.rolling_summary_update.logic import update_summary
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.schemas.provider import LLMResponse, TokenUsage


def _response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        parsed_json=None,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def test_update_summary_invokes_llm_with_canonical_prompt() -> None:
    client = DeterministicFakeClient(
        scripted_responses={
            "archivist.rolling_summary_update": _response(
                "The PC met Marcus at the Bent Copper and accepted Sera's plea."
            )
        }
    )

    summary = update_summary(
        old_summary="The PC arrived in Rivermouth.",
        new_transcript_snippets=["Sera asked for help finding Dav."],
        scene_brief={"location": "Bent Copper Tavern"},
        llm_client=client,
        token_cap=50,
    )

    assert summary == "The PC met Marcus at the Bent Copper and accepted Sera's plea."


def test_update_summary_truncates_over_token_cap() -> None:
    client = DeterministicFakeClient(
        scripted_responses={
            "archivist.rolling_summary_update": _response("one two three four five six seven eight")
        }
    )

    summary = update_summary(
        old_summary=None,
        new_transcript_snippets=["Events happened."],
        scene_brief={},
        llm_client=client,
        token_cap=3,
    )

    assert len(summary.split()) <= 3
