"""LLM-driven canonical rolling summary updates at scene boundaries."""

from __future__ import annotations

from typing import Any

from sagasmith.providers import LLMClient
from sagasmith.schemas.common import estimate_tokens
from sagasmith.schemas.provider import LLMRequest, Message


def update_summary(
    old_summary: str | None,
    new_transcript_snippets: list[str],
    scene_brief: dict[str, Any],
    llm_client: LLMClient,
    token_cap: int = 800,
) -> str:
    """Update the rolling campaign summary using constrained text completion."""

    prompt = _build_prompt(
        old_summary=old_summary or "",
        new_transcript_snippets=new_transcript_snippets,
        scene_brief=scene_brief,
        token_cap=token_cap,
    )
    request = LLMRequest(
        agent_name="archivist.rolling_summary_update",
        model="default",
        messages=[
            Message(
                role="system",
                content=(
                    "You update a tabletop RPG campaign rolling summary. "
                    "Preserve only canonical, player-observable facts. Do not add speculation."
                ),
            ),
            Message(role="user", content=prompt),
        ],
        response_format="text",
        temperature=0.0,
        max_tokens=max(32, token_cap),
        timeout_seconds=60,
        metadata={"skill": "rolling-summary-update"},
    )
    response = llm_client.complete(request)
    return _truncate_to_token_cap(response.text.strip(), token_cap=token_cap)


def _build_prompt(
    *,
    old_summary: str,
    new_transcript_snippets: list[str],
    scene_brief: dict[str, Any],
    token_cap: int,
) -> str:
    snippets = "\n".join(f"- {line}" for line in new_transcript_snippets if line.strip())
    brief_lines = "\n".join(f"{key}: {value}" for key, value in scene_brief.items())
    return (
        "Given the following rolling summary and the latest scene events, produce an "
        f"updated canonical summary that preserves only verifiable facts and stays within ~{token_cap} tokens. "
        "Do not add speculation.\n\n"
        f"Current rolling summary:\n{old_summary or '(none)'}\n\n"
        f"Scene brief:\n{brief_lines or '(none)'}\n\n"
        f"Latest scene events:\n{snippets or '(none)'}"
    )


def _truncate_to_token_cap(text: str, *, token_cap: int) -> str:
    if token_cap <= 0:
        return ""
    if estimate_tokens(text) <= token_cap:
        return text
    words = text.split()
    while words and estimate_tokens(" ".join(words)) > token_cap:
        words.pop()
    return " ".join(words)
