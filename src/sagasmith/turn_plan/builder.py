"""Turn Plan: assemble the Archivist's work for one turn.

Consumes state and injected collaborators; produces a TurnPlan value.
Never performs SQLite or vault writes — that is the runtime's turn_close
responsibility (ADR-0001 lines 113-116).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import yaml

from sagasmith.agents.archivist.skills.canon_conflict_detection.logic import detect_conflicts
from sagasmith.agents.archivist.skills.entity_resolution.logic import resolve_entity
from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import assemble_memory_packet
from sagasmith.agents.archivist.skills.rolling_summary_update.logic import update_summary
from sagasmith.agents.archivist.skills.vault_page_upsert.logic import vault_page_upsert
from sagasmith.agents.archivist.skills.visibility_promotion.logic import promote_visibility
from sagasmith.providers.client import LLMClient
from sagasmith.schemas.deltas import CanonConflict
from sagasmith.schemas.narrative import MemoryPacket
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter


@dataclass(frozen=True)
class TurnPlanContext:
    """Everything build_turn_plan needs. Plain mappings and injected collaborators."""

    state: Mapping[str, Any]
    vault_service: VaultService | None
    transcript_conn: sqlite3.Connection | None
    llm: LLMClient | None


@dataclass(frozen=True)
class TurnPlan:
    """Result of build_turn_plan: everything the Adapter needs to project onto state."""

    session_state: Mapping[str, Any]
    rolling_summary: Any
    pending_conflicts: Sequence[CanonConflict]
    memory_packet: MemoryPacket
    pending_vault_writes: tuple[VaultPage, ...]
    pending_narration: Sequence[str]


def build_turn_plan(context: TurnPlanContext) -> TurnPlan:
    """Produce the Archivist's turn plan from state and collaborators.

    Composes entity resolution, vault-page upsert, visibility promotion,
    rolling summary update, canon conflict detection, and memory packet
    assembly into a single explicit TurnPlan value.
    """
    state = context.state
    vault_service = context.vault_service

    session_state = dict(state["session_state"])
    session_state["turn_count"] = session_state.get("turn_count", 0) + 1
    session_number = session_state.get("session_number", 1)

    pending_writes: list[VaultPage] = []

    # Persist WorldBible and CampaignSeed on first turn-close
    if vault_service is not None and session_state["turn_count"] == 1:
        world_bible = state.get("world_bible")
        if world_bible is not None:
            frontmatter = LoreFrontmatter(
                id="world_bible",
                type="lore",
                name="World Bible",
                aliases=[],
                visibility="gm_only",
                first_encountered=str(session_number),
                category="world_bible",
            )
            wb_data = (
                world_bible
                if isinstance(world_bible, dict)
                else world_bible.model_dump(mode="json")
            )
            pending_writes.append(
                VaultPage(frontmatter, yaml.safe_dump(wb_data, sort_keys=False, allow_unicode=True))
            )

        campaign_seed = state.get("campaign_seed")
        if campaign_seed is not None:
            frontmatter = LoreFrontmatter(
                id="campaign_seed",
                type="lore",
                name="Campaign Seed",
                aliases=[],
                visibility="gm_only",
                first_encountered=str(session_number),
                category="campaign_seed",
            )
            cs_data = (
                campaign_seed
                if isinstance(campaign_seed, dict)
                else campaign_seed.model_dump(mode="json")
            )
            pending_writes.append(
                VaultPage(frontmatter, yaml.safe_dump(cs_data, sort_keys=False, allow_unicode=True))
            )

    # Process present entities from scene_brief
    scene_brief_raw = state.get("scene_brief") or {}
    scene_brief: dict[str, Any] = scene_brief_raw if isinstance(scene_brief_raw, dict) else {}
    present_entities_raw = scene_brief.get("present_entities", [])
    present_entities = (
        [v for v in present_entities_raw if isinstance(v, str)]
        if isinstance(present_entities_raw, list)
        else []
    )
    if vault_service is not None and present_entities:
        queued_names: set[str] = set()
        for entity_name in present_entities:
            normalized = entity_name.strip().casefold()
            if not normalized or normalized in queued_names:
                continue
            queued_names.add(normalized)
            resolved = _resolve_known_entity(vault_service, entity_name)
            if resolved is not None:
                promoted = _promote_existing_page(
                    page=resolved,
                    context={
                        "scene_brief": scene_brief,
                        "player_input": state.get("pending_player_input"),
                        "pending_narration": state.get("pending_narration", []),
                    },
                )
                if promoted is not None:
                    pending_writes.append(promoted)
                continue
            draft: dict[str, object] = {
                "name": entity_name,
                "type": "npc",
                "species": "unknown",
                "role": "unknown",
                "status": "alive",
                "disposition_to_pc": "neutral",
            }
            if entity_name.startswith("npc_"):
                draft["id"] = entity_name
            try:
                result = vault_page_upsert(
                    vault_service=vault_service,
                    entity_draft=draft,
                    visibility="player_known",
                    session_number=session_number,
                )
                pending_writes.append(result.page)
            except ValueError:
                pass

    rolling_summary = _maybe_update_rolling_summary(
        state=state,
        llm=context.llm,
        scene_brief=scene_brief,
    )

    # Rolling summary meta page
    if vault_service is not None and isinstance(rolling_summary, str):
        frontmatter = LoreFrontmatter(
            id="rolling_summary",
            type="lore",
            name="Rolling Summary",
            aliases=[],
            visibility="gm_only",
            first_encountered=str(session_number),
            category="rolling_summary",
        )
        pending_writes.append(VaultPage(frontmatter, rolling_summary))

    promotion_context = {
        "scene_brief": scene_brief,
        "player_input": state.get("pending_player_input"),
        "pending_narration": state.get("pending_narration", []),
    }
    if pending_writes:
        pending_writes = _promote_pending_pages(pending_writes, context=promotion_context)

    player_input = state.get("pending_player_input")
    pending_conflicts = detect_conflicts(
        player_input if isinstance(player_input, str) else "",
        pending_writes,
    )

    memory_packet = assemble_memory_packet(
        {**state, "rolling_summary": rolling_summary},
        conn=context.transcript_conn,
        vault_service=vault_service,
    )

    return TurnPlan(
        session_state=session_state,
        rolling_summary=rolling_summary,
        pending_conflicts=pending_conflicts,
        memory_packet=memory_packet,
        pending_vault_writes=tuple(pending_writes),
        pending_narration=list(state.get("pending_narration", [])),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_known_entity(vault_service: VaultService, entity_name: str) -> VaultPage | None:
    for entity_type in ("npc", "location", "faction", "item", "quest", "callback", "lore"):
        page, status = resolve_entity(entity_name, entity_type, vault_service.resolver)
        if status == "matched":
            return page
    page, status = resolve_entity(entity_name, None, vault_service.resolver)
    return page if status == "matched" else None


def _promote_pending_pages(pages: list[VaultPage], *, context: dict[str, Any]) -> list[VaultPage]:
    promoted: list[VaultPage] = []
    for page in pages:
        new_visibility = promote_visibility(page, context)
        if new_visibility != page.frontmatter.visibility:
            promoted.append(
                VaultPage(
                    page.frontmatter.model_copy(update={"visibility": new_visibility}),
                    page.body,
                )
            )
        else:
            promoted.append(page)
    return promoted


def _promote_existing_page(*, page: VaultPage, context: dict[str, Any]) -> VaultPage | None:
    """Return a visibility-promoted copy or None if no change needed."""
    new_visibility = promote_visibility(page, context)
    if new_visibility == page.frontmatter.visibility:
        return None
    return VaultPage(page.frontmatter.model_copy(update={"visibility": new_visibility}), page.body)


def _maybe_update_rolling_summary(
    *,
    state: Mapping[str, Any],
    llm: LLMClient | None,
    scene_brief: dict[str, Any],
) -> Any:
    old_summary = state.get("rolling_summary")
    needs_initial = not isinstance(old_summary, str) or not old_summary.strip()
    if llm is None or (
        not needs_initial and not _is_scene_boundary(state=state, scene_brief=scene_brief)
    ):
        return old_summary
    snippets = _summary_snippets(state)
    if not snippets and not scene_brief:
        return old_summary
    return update_summary(
        old_summary=old_summary if isinstance(old_summary, str) else None,
        new_transcript_snippets=snippets,
        scene_brief=scene_brief,
        llm_client=llm,
        token_cap=800,
    )


def _is_scene_boundary(*, state: Mapping[str, Any], scene_brief: dict[str, Any]) -> bool:
    if bool(state.get("oracle_bypass_detected")):
        return True
    previous_id = state.get("previous_scene_id")
    current_id = scene_brief.get("scene_id")
    if isinstance(previous_id, str) and isinstance(current_id, str) and previous_id != current_id:
        return True
    beat_ids = scene_brief.get("beat_ids")
    resolved = state.get("resolved_beat_ids", [])
    if isinstance(beat_ids, list) and beat_ids:
        resolved_set = (
            {v for v in resolved if isinstance(v, str)} if isinstance(resolved, list) else set()
        )
        return all(isinstance(v, str) and v in resolved_set for v in beat_ids)
    beats = scene_brief.get("beats")
    resolved_beats = state.get("resolved_beats", [])
    if isinstance(beats, list) and beats:
        resolved_set = (
            {v for v in resolved_beats if isinstance(v, str)}
            if isinstance(resolved_beats, list)
            else set()
        )
        return all(isinstance(v, str) and v in resolved_set for v in beats)
    return False


def _summary_snippets(state: Mapping[str, Any]) -> list[str]:
    snippets: list[str] = []
    player_input = state.get("pending_player_input")
    if isinstance(player_input, str) and player_input.strip():
        snippets.append(f"Player: {player_input.strip()}")
    pending_narration = state.get("pending_narration", [])
    if isinstance(pending_narration, list):
        snippets.extend(v.strip() for v in pending_narration if isinstance(v, str) and v.strip())
    return snippets
