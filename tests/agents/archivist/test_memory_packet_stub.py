"""Tests for Phase 6 MemoryPacket stub assembly."""

from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from sagasmith.agents.archivist.entity_stubs import stub_entity_refs
from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet_stub,
)
from sagasmith.evals.fixtures import make_valid_saga_state
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.schemas.common import estimate_tokens
from sagasmith.schemas.narrative import MemoryPacket


def _conn_with_turn(content: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("turn_000001", "cmp_001", "sess_001", "complete", "2026-01-01T00:00:00Z", "2026-01-01T00:00:10Z", 1),
    )
    conn.execute(
        "INSERT INTO transcript_entries (turn_id, kind, content, sequence, created_at) VALUES (?, ?, ?, ?, ?)",
        ("turn_000001", "narration_final", content, 0, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    return conn


def test_memory_packet_model_rejects_over_cap_data() -> None:
    with pytest.raises(ValidationError, match="token_cap"):
        MemoryPacket(
            token_cap=1,
            summary="x" * 100,
            entities=[],
            recent_turns=[],
            open_callbacks=[],
            retrieval_notes=[],
        )


def test_assembly_uses_recent_transcript_and_enforces_token_cap() -> None:
    state = make_valid_saga_state(campaign_id="cmp_001", memory_packet=None).model_dump()
    conn = _conn_with_turn("Marcus led the hero through Rivermouth Market." * 20)

    packet = assemble_memory_packet_stub(state, conn=conn, token_cap=30)

    estimated = estimate_tokens(packet.summary) + sum(estimate_tokens(line) for line in packet.recent_turns)
    assert estimated <= packet.token_cap
    assert packet.token_cap == 30
    assert packet.retrieval_notes[0].startswith("Phase 6 stub")


def test_entity_reference_stubs_are_stable_and_provisional() -> None:
    refs = stub_entity_refs(
        location="Rivermouth Market",
        present_entities=["Captain Vela"],
        recent_turns=["Marcus met Vela near the Old Bridge."],
    )

    ids = {ref.entity_id for ref in refs}
    assert "location_rivermouth_market" in ids
    assert "npc_captain_vela" in ids
    assert "npc_marcus" in ids
    assert all(ref.provisional for ref in refs)


def test_assembly_falls_back_to_current_state_without_full_archivist() -> None:
    state = make_valid_saga_state(
        campaign_id="cmp_001",
        memory_packet=None,
        pending_player_input="look for Marcus",
    ).model_dump()

    packet = assemble_memory_packet_stub(state, conn=None, token_cap=128)

    assert packet.recent_turns == ["current:player_input: look for Marcus"]
    assert any("SQLite connection unavailable" in note for note in packet.retrieval_notes)
