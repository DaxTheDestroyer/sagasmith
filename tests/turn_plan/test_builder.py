"""Tests for the Turn Plan Module Interface.

All tests call build_turn_plan directly — no LangGraph or Textual plumbing.
Collaborators: real VaultService on tmp_path, :memory: sqlite, DeterministicFakeClient.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

import sagasmith.vault.paths as vp
from sagasmith.evals.fixtures import make_valid_saga_state, make_valid_scene_brief
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.providers.fake import DeterministicFakeClient
from sagasmith.schemas.narrative import MemoryPacket
from sagasmith.schemas.provider import LLMResponse, TokenUsage
from sagasmith.turn_plan import TurnPlanContext, build_turn_plan
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import NpcFrontmatter

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


def _fake_llm(summary_text: str = "Updated summary.") -> DeterministicFakeClient:
    usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return DeterministicFakeClient(
        scripted_responses={
            "archivist.rolling_summary_update": LLMResponse(
                text=summary_text, usage=usage, finish_reason="stop"
            )
        }
    )


def _ctx(
    state: dict[str, Any] | None = None,
    *,
    vault_service: VaultService | None = None,
    transcript_conn: sqlite3.Connection | None = None,
    llm: DeterministicFakeClient | None = None,
) -> TurnPlanContext:
    return TurnPlanContext(
        state=state if state is not None else make_valid_saga_state().model_dump(),
        vault_service=vault_service,
        transcript_conn=transcript_conn,
        llm=llm,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_session_state_turn_count_incremented() -> None:
    state = make_valid_saga_state().model_dump()
    assert state["session_state"]["turn_count"] == 0
    plan = build_turn_plan(_ctx(state))
    assert plan.session_state["turn_count"] == 1


def test_first_turn_emits_world_bible_page(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["world_bible"] = {"setting": "Fantasy", "tone": "gritty"}
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    ids = [p.frontmatter.id for p in plan.pending_vault_writes]
    assert "world_bible" in ids


def test_first_turn_emits_campaign_seed_page(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["campaign_seed"] = {"hook": "Ancient dragon awakens"}
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    ids = [p.frontmatter.id for p in plan.pending_vault_writes]
    assert "campaign_seed" in ids


def test_subsequent_turn_does_not_re_emit_world_bible(vault: VaultService) -> None:
    from sagasmith.evals.fixtures import make_valid_session_state

    state = make_valid_saga_state(session_state=make_valid_session_state(turn_count=1)).model_dump()
    state["world_bible"] = {"setting": "Fantasy"}
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    ids = [p.frontmatter.id for p in plan.pending_vault_writes]
    assert "world_bible" not in ids


def test_present_entities_become_npc_pages(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["scene_brief"] = make_valid_scene_brief(present_entities=["Marcus"]).model_dump()
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    ids = [p.frontmatter.id for p in plan.pending_vault_writes]
    assert "npc_marcus" in ids
    # Vault is never written: the file must not exist
    assert not (vault.master_path / "npcs" / "npc_marcus.md").exists()


def test_existing_entity_promoted_not_recreated(vault: VaultService) -> None:
    # Pre-write a gm_only NPC page so the resolver can find it
    vault.ensure_master_path()
    existing = VaultPage(
        NpcFrontmatter(
            id="npc_marcus",
            type="npc",
            name="Marcus",
            aliases=[],
            visibility="gm_only",
            first_encountered="1",
            species="human",
            role="merchant",
            status="alive",
            disposition_to_pc="neutral",
        ),
        "",
    )
    vault.write_page(existing, Path("npcs/npc_marcus.md"))
    vault.resolver.refresh()

    state = make_valid_saga_state().model_dump()
    state["scene_brief"] = make_valid_scene_brief(present_entities=["Marcus"]).model_dump()
    plan = build_turn_plan(_ctx(state, vault_service=vault))

    # Marcus should be in pending_vault_writes as a promoted copy, not a new creation
    marcus_pages = [p for p in plan.pending_vault_writes if p.frontmatter.id == "npc_marcus"]
    assert len(marcus_pages) == 1
    assert marcus_pages[0].frontmatter.visibility == "player_known"


def test_rolling_summary_unchanged_when_llm_absent() -> None:
    state = make_valid_saga_state().model_dump()
    state["rolling_summary"] = "Original summary."
    plan = build_turn_plan(_ctx(state, llm=None))
    assert plan.rolling_summary == "Original summary."


def test_rolling_summary_updates_at_scene_boundary(
    vault: VaultService, conn: sqlite3.Connection
) -> None:
    state = make_valid_saga_state().model_dump()
    state["rolling_summary"] = "Old summary."
    state["oracle_bypass_detected"] = True  # triggers scene boundary
    state["pending_player_input"] = "I walk into the tavern."
    plan = build_turn_plan(
        _ctx(state, vault_service=vault, transcript_conn=conn, llm=_fake_llm("New summary."))
    )
    assert plan.rolling_summary == "New summary."


def test_rolling_summary_meta_page_emitted(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["rolling_summary"] = "Some summary text."
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    ids = [p.frontmatter.id for p in plan.pending_vault_writes]
    assert "rolling_summary" in ids
    rolling_page = next(
        p for p in plan.pending_vault_writes if p.frontmatter.id == "rolling_summary"
    )
    assert rolling_page.body == "Some summary text."


def test_visibility_promotion_applied_to_all_pending_writes(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["scene_brief"] = make_valid_scene_brief(present_entities=["Marcus"]).model_dump()
    state["rolling_summary"] = "Existing summary."
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    # All entity pages should be player_known since they're in present_entities
    entity_pages = [p for p in plan.pending_vault_writes if p.frontmatter.type == "npc"]
    for page in entity_pages:
        assert page.frontmatter.visibility == "player_known"


def test_memory_packet_assembled_with_updated_rolling_summary(
    vault: VaultService, conn: sqlite3.Connection
) -> None:
    state = make_valid_saga_state().model_dump()
    state["oracle_bypass_detected"] = True
    state["pending_player_input"] = "I look around."
    plan = build_turn_plan(
        _ctx(state, vault_service=vault, transcript_conn=conn, llm=_fake_llm("Refreshed summary."))
    )
    assert isinstance(plan.memory_packet, MemoryPacket)
    assert plan.memory_packet.summary == "Refreshed summary."


def test_pending_conflicts_returned_as_sequence() -> None:
    # detect_conflicts is a Phase-7 stub that always returns []
    plan = build_turn_plan(_ctx())
    assert list(plan.pending_conflicts) == []


def test_returns_real_vault_page_objects(vault: VaultService) -> None:
    state = make_valid_saga_state().model_dump()
    state["scene_brief"] = make_valid_scene_brief(present_entities=["Orym"]).model_dump()
    plan = build_turn_plan(_ctx(state, vault_service=vault))
    for page in plan.pending_vault_writes:
        assert isinstance(page, VaultPage), f"Expected VaultPage, got {type(page)}"


def test_pending_narration_passthrough() -> None:
    state = make_valid_saga_state().model_dump()
    state["pending_narration"] = ["The fire crackles.", "A crow caws."]
    plan = build_turn_plan(_ctx(state))
    assert list(plan.pending_narration) == ["The fire crackles.", "A crow caws."]
