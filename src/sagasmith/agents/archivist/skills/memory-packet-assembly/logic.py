"""Phase 6 MemoryPacket stub assembly logic."""

from __future__ import annotations

import sqlite3
from typing import Any

from sagasmith.agents.archivist.entity_stubs import stub_entity_refs
from sagasmith.agents.archivist.transcript_context import (
    format_transcript_context,
    get_recent_transcript_context,
)
from sagasmith.schemas.common import estimate_tokens
from sagasmith.schemas.narrative import MemoryPacket

DEFAULT_MEMORY_TOKEN_CAP = 512
RECENT_TRANSCRIPT_LIMIT = 8


def assemble_memory_packet_stub(
    state: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    token_cap: int = DEFAULT_MEMORY_TOKEN_CAP,
) -> MemoryPacket:
    """Assemble a bounded, no-LLM MemoryPacket from current state and SQLite context."""

    campaign_id = str(state.get("campaign_id", ""))
    scene_brief = state.get("scene_brief") or {}
    if not isinstance(scene_brief, dict):
        scene_brief = {}

    transcript_entries = get_recent_transcript_context(
        conn,
        campaign_id=campaign_id,
        limit=RECENT_TRANSCRIPT_LIMIT,
    )
    recent_turns = format_transcript_context(transcript_entries)
    if not recent_turns:
        recent_turns = _fallback_recent_context(state)

    summary = _build_summary(state, scene_brief=scene_brief, recent_turns=recent_turns)
    location = scene_brief.get("location") if isinstance(scene_brief.get("location"), str) else None
    present_entities = [
        value for value in scene_brief.get("present_entities", []) if isinstance(value, str)
    ]
    entities = stub_entity_refs(
        location=location,
        present_entities=present_entities,
        recent_turns=recent_turns,
    )
    retrieval_notes = [
        "Phase 6 stub: recent transcript context only; full vault retrieval deferred to Phase 7."
    ]
    if conn is None:
        retrieval_notes.append("SQLite connection unavailable; used graph-state fallback context.")

    bounded_summary, bounded_turns = _enforce_cap(summary, recent_turns, token_cap=token_cap)
    return MemoryPacket(
        token_cap=token_cap,
        summary=bounded_summary,
        entities=entities,
        recent_turns=bounded_turns,
        open_callbacks=[],
        retrieval_notes=retrieval_notes,
    )


def _fallback_recent_context(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    pending_input = state.get("pending_player_input")
    if isinstance(pending_input, str) and pending_input:
        lines.append(f"current:player_input: {pending_input}")
    for index, line in enumerate(state.get("pending_narration", [])):
        if isinstance(line, str) and line:
            lines.append(f"current:{index}:narration_final: {line}")
    return lines


def _build_summary(
    state: dict[str, Any], *, scene_brief: dict[str, Any], recent_turns: list[str]
) -> str:
    session_state = state.get("session_state") or {}
    if not isinstance(session_state, dict):
        session_state = {}
    turn_count = session_state.get("turn_count", 0)
    intent = scene_brief.get("intent")
    location = scene_brief.get("location")
    parts = [f"Turn {turn_count} memory stub."]
    if isinstance(intent, str) and intent:
        parts.append(f"Scene intent: {intent}.")
    if isinstance(location, str) and location:
        parts.append(f"Location: {location}.")
    if recent_turns:
        parts.append("Recent transcript context is available for continuity.")
    else:
        parts.append("No prior transcript context is available yet.")
    return " ".join(parts)


def _enforce_cap(summary: str, recent_turns: list[str], *, token_cap: int) -> tuple[str, list[str]]:
    bounded_turns = list(recent_turns)
    bounded_summary = summary
    while _packet_tokens(bounded_summary, bounded_turns) > token_cap and bounded_turns:
        bounded_turns.pop(0)
    while _packet_tokens(bounded_summary, bounded_turns) > token_cap and bounded_summary:
        bounded_summary = bounded_summary[: max(0, len(bounded_summary) - 16)].rstrip()
    return bounded_summary, bounded_turns


def _packet_tokens(summary: str, recent_turns: list[str]) -> int:
    return estimate_tokens(summary) + sum(estimate_tokens(turn) for turn in recent_turns)
