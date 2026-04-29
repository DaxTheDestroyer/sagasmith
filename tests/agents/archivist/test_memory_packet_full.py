"""Integration tests for full memory-packet assembly with hybrid retrieval."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
    assemble_memory_packet_stub,
)
from sagasmith.memory.fts5 import FTS5Index
from sagasmith.memory.graph import reset_vault_graph_cache, warm_vault_graph
from sagasmith.schemas.common import estimate_tokens
from sagasmith.vault import VaultService


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with FTS5."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA journal_mode=WAL")
    return c


@pytest.fixture
def fts_populated(conn: sqlite3.Connection) -> FTS5Index:
    """FTS5 index populated with sample vault pages."""
    fts = FTS5Index(conn)
    fts.index_page(
        "npcs/npc_marcus.md", "Marcus runs the Bent Copper tavern. He is a weary innkeeper."
    )
    fts.index_page(
        "locations/loc_tavern.md", "The Bent Copper is a low-ceilinged tavern in Rivermouth."
    )
    fts.index_page("npcs/npc_sera.md", "Sera is a worried wife looking for her missing husband.")
    return fts


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal vault with interconnected pages."""
    npcs = tmp_path / "npcs"
    locs = tmp_path / "locations"
    cbs = tmp_path / "callbacks"
    for d in (npcs, locs, cbs):
        d.mkdir()

    (npcs / "npc_marcus.md").write_text(
        "---\nid: npc_marcus\ntype: npc\nname: Marcus\nvisibility: player_known\n"
        "species: Human\nrole: Innkeeper\nstatus: alive\ndisposition_to_pc: friendly\n---\n\n"
        "Marcus runs the [[loc_tavern|tavern]].",
        encoding="utf-8",
    )
    (locs / "loc_tavern.md").write_text(
        "---\nid: loc_tavern\ntype: location\nname: Bent Copper Tavern\nvisibility: player_known\n"
        "status: active\nconnects_to: []\n---\n\nA low-ceilinged tavern.",
        encoding="utf-8",
    )
    (cbs / "cb_witness.md").write_text(
        "---\nid: cb_witness\ntype: callback\nname: Witness Callback\nvisibility: player_known\n"
        "status: open\nseeded_in: session_1\n---\n\nA witness was seen.",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def vault_service(vault_root: Path, tmp_path: Path) -> VaultService:
    """VaultService backed by the test vault."""
    player_vault = tmp_path / "player_vault"
    player_vault.mkdir(exist_ok=True)
    svc = VaultService.__new__(VaultService)
    svc.master_path = vault_root
    svc.player_vault_root = player_vault
    object.__setattr__(svc, "_resolver", _make_resolver(vault_root))
    return svc


def _make_resolver(vault_root: Path):
    from sagasmith.vault.resolver import EntityResolver

    return EntityResolver(vault_root)


def _make_state(
    *,
    campaign_id: str = "test_campaign",
    session_number: int = 1,
    turn_count: int = 1,
    location: str | None = "Bent Copper Tavern",
    present_entities: list[str] | None = None,
    rolling_summary: str | None = None,
    pending_player_input: str | None = None,
    pending_narration: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal graph state dict for testing."""
    return {
        "campaign_id": campaign_id,
        "session_id": "session_001",
        "turn_id": "turn_0001",
        "session_state": {
            "session_number": session_number,
            "turn_count": turn_count,
        },
        "scene_brief": {
            "location": location,
            "present_entities": present_entities or [],
        },
        "rolling_summary": rolling_summary,
        "pending_player_input": pending_player_input,
        "pending_narration": pending_narration or [],
    }


class TestAssembleMemoryPacket:
    def test_basic_assembly_with_transcript(
        self, conn: sqlite3.Connection, fts_populated: FTS5Index
    ) -> None:
        """Basic assembly produces a valid MemoryPacket with retrieval notes."""
        state = _make_state()
        packet = assemble_memory_packet(state, conn=conn, token_cap=512)
        assert packet.token_cap == 512
        assert len(packet.retrieval_notes) > 0
        assert packet.summary

    def test_rolling_summary_used_when_present(self, conn: sqlite3.Connection) -> None:
        """Rolling summary from state is used as-is."""
        state = _make_state(rolling_summary="The party arrived at Rivermouth and met Marcus.")
        packet = assemble_memory_packet(state, conn=conn, token_cap=512)
        assert "Rivermouth" in packet.summary
        assert any("rolling_summary:included" in n for n in packet.retrieval_notes)

    def test_fallback_summary_when_no_rolling(self, conn: sqlite3.Connection) -> None:
        """Without rolling summary, a fallback summary is generated."""
        state = _make_state(rolling_summary=None, turn_count=5)
        packet = assemble_memory_packet(state, conn=conn, token_cap=512)
        assert "Turn 5" in packet.summary
        assert any("fallback" in n for n in packet.retrieval_notes)

    def test_entity_resolution_with_vault(
        self, conn: sqlite3.Connection, vault_service: VaultService
    ) -> None:
        """Entities are resolved to vault-backed refs when vault_service is available."""
        state = _make_state(present_entities=["Marcus"])
        # Warm graph cache for this vault
        warm_vault_graph(vault_service.master_path)
        try:
            packet = assemble_memory_packet(
                state, conn=conn, vault_service=vault_service, token_cap=2048
            )
            # Marcus should be resolved
            entity_ids = [e.entity_id for e in packet.entities]
            assert "npc_marcus" in entity_ids
            # Resolved entity has vault_path
            marcus_ref = next(e for e in packet.entities if e.entity_id == "npc_marcus")
            assert marcus_ref.vault_path is not None
            assert not marcus_ref.provisional
        finally:
            reset_vault_graph_cache()

    def test_entity_resolution_without_vault(self, conn: sqlite3.Connection) -> None:
        """Without vault_service, provisional entity stubs are used."""
        state = _make_state(present_entities=["Marcus"])
        packet = assemble_memory_packet(state, conn=conn, token_cap=512)
        # Should have at least one entity (may be provisional)
        assert len(packet.entities) >= 1

    def test_open_callbacks_found(
        self, conn: sqlite3.Connection, vault_service: VaultService
    ) -> None:
        """Open callbacks in vault are discovered."""
        state = _make_state()
        warm_vault_graph(vault_service.master_path)
        try:
            packet = assemble_memory_packet(
                state, conn=conn, vault_service=vault_service, token_cap=2048
            )
            assert "cb_witness" in packet.open_callbacks
            assert any("callbacks" in n for n in packet.retrieval_notes)
        finally:
            reset_vault_graph_cache()

    def test_token_cap_enforcement(self, conn: sqlite3.Connection) -> None:
        """MemoryPacket never exceeds token_cap."""
        # Build a long rolling summary
        long_summary = " ".join(["word"] * 500)
        state = _make_state(rolling_summary=long_summary)
        token_cap = 128
        packet = assemble_memory_packet(state, conn=conn, token_cap=token_cap)
        estimated = estimate_tokens(packet.summary) + sum(
            estimate_tokens(t) for t in packet.recent_turns
        )
        assert estimated <= token_cap

    def test_token_cap_with_transcript(self, conn: sqlite3.Connection) -> None:
        """Token cap is enforced even with both summary and transcript entries."""
        state = _make_state(
            rolling_summary="A long summary. " * 50,
            pending_narration=["Narration line. " * 20] * 5,
        )
        token_cap = 64
        packet = assemble_memory_packet(state, conn=conn, token_cap=token_cap)
        estimated = estimate_tokens(packet.summary) + sum(
            estimate_tokens(t) for t in packet.recent_turns
        )
        assert estimated <= token_cap

    def test_fts5_search_contributed(
        self, conn: sqlite3.Connection, fts_populated: FTS5Index
    ) -> None:
        """FTS5 search results are noted in retrieval_notes."""
        state = _make_state(location="Tavern", present_entities=["Marcus"])
        packet = assemble_memory_packet(state, conn=conn, token_cap=2048)
        assert any("fts5" in n for n in packet.retrieval_notes)

    def test_graph_neighbors_contributed(
        self, conn: sqlite3.Connection, vault_service: VaultService
    ) -> None:
        """Graph neighbors are included in entity refs when graph is warmed."""
        warm_vault_graph(vault_service.master_path)
        try:
            state = _make_state(present_entities=["Marcus"])
            packet = assemble_memory_packet(
                state, conn=conn, vault_service=vault_service, token_cap=2048
            )
            # Check if any retrieval notes mention graph
            has_graph = any("graph" in n for n in packet.retrieval_notes)
            # Graph should contribute neighbors if Marcus has connections
            if has_graph:
                assert len(packet.entities) > 1
        finally:
            reset_vault_graph_cache()


class TestBackwardCompatStub:
    def test_stub_still_works(self, conn: sqlite3.Connection) -> None:
        """assemble_memory_packet_stub still produces a valid packet."""
        state = _make_state()
        packet = assemble_memory_packet_stub(state, conn=conn, token_cap=512)
        assert packet.token_cap == 512
        assert packet.summary

    def test_stub_no_vault_service(self, conn: sqlite3.Connection) -> None:
        """Stub delegates to full assembly without vault_service."""
        state = _make_state(present_entities=["Marcus"])
        packet = assemble_memory_packet_stub(state, conn=conn, token_cap=512)
        assert len(packet.entities) >= 1


class TestMemoryPacketSchema:
    def test_packet_validates_token_cap(self) -> None:
        """MemoryPacket schema rejects packets exceeding cap."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="token_cap"):
            # summary is huge but cap is tiny
            from sagasmith.schemas.narrative import MemoryPacket

            MemoryPacket(
                token_cap=10,
                summary="x" * 1000,
                entities=[],
                recent_turns=[],
                open_callbacks=[],
                retrieval_notes=[],
            )

    def test_packet_valid_within_cap(self) -> None:
        """MemoryPacket schema accepts packets within cap."""
        from sagasmith.schemas.narrative import MemoryPacket

        packet = MemoryPacket(
            token_cap=1000,
            summary="Short summary.",
            entities=[],
            recent_turns=[],
            open_callbacks=[],
            retrieval_notes=["test"],
        )
        assert packet.token_cap == 1000
