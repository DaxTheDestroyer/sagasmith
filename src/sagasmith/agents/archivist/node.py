"""Archivist agent node."""

from __future__ import annotations

from typing import Any

import yaml

from sagasmith.agents.archivist.skills.canon_conflict_detection.logic import detect_conflicts
from sagasmith.agents.archivist.skills.entity_resolution.logic import resolve_entity
from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
)
from sagasmith.agents.archivist.skills.rolling_summary_update.logic import update_summary
from sagasmith.agents.archivist.skills.vault_page_upsert.logic import (
    vault_page_upsert,
)
from sagasmith.agents.archivist.skills.visibility_promotion.logic import promote_visibility
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.world import WorldBible
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter


def archivist_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Assemble memory packet, persist entity pages to vault, and return vault writes."""
    if getattr(services, "_call_recorder", None) is not None:
        services._call_recorder.append("archivist")
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None:
            for skill_name in [
                "entity-resolution",
                "vault-page-upsert",
                "visibility-promotion",
                "rolling-summary-update",
                "session-page-authoring",
                "canon-conflict-detection",
                "memory-packet-assembly",
            ]:
                if store.find(name=skill_name, agent_scope="archivist") is not None:
                    activation.set_skill(skill_name)

    session_state = dict(state["session_state"])
    session_state["turn_count"] = session_state.get("turn_count", 0) + 1
    session_number = session_state.get("session_number", 1)

    vault_pending_writes: list[VaultPage] = []

    vault_service: VaultService | None = getattr(services, "vault_service", None)

    # Persist WorldBible and CampaignSeed on first turn-close
    if vault_service is not None and session_state["turn_count"] == 1:
        world_bible: WorldBible | None = state.get("world_bible")
        if world_bible is not None:
            # Serialize WorldBible to YAML in body, use Lore frontmatter with category="world_bible"
            frontmatter = LoreFrontmatter(
                id="world_bible",
                type="lore",
                name="World Bible",
                aliases=[],
                visibility="gm_only",
                first_encountered=str(session_number),
                category="world_bible",
            )
            # State may store WorldBible as a dict (serialized) or pydantic model
            wb_data = (
                world_bible
                if isinstance(world_bible, dict)
                else world_bible.model_dump(mode="json")
            )
            body = yaml.safe_dump(wb_data, sort_keys=False, allow_unicode=True)
            page = VaultPage(frontmatter, body)
            vault_pending_writes.append(page)

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
            body = yaml.safe_dump(cs_data, sort_keys=False, allow_unicode=True)
            page = VaultPage(frontmatter, body)
            vault_pending_writes.append(page)

    # Process present entities from scene_brief: write new entity pages
    scene_brief_raw = state.get("scene_brief") or {}
    scene_brief: dict[str, Any] = scene_brief_raw if isinstance(scene_brief_raw, dict) else {}
    present_entities_raw = scene_brief.get("present_entities", [])
    present_entities = (
        [value for value in present_entities_raw if isinstance(value, str)]
        if isinstance(present_entities_raw, list)
        else []
    )
    if vault_service is not None and present_entities:
        queued_names: set[str] = set()
        for entity_name in present_entities:
            normalized_name = entity_name.strip().casefold()
            if not normalized_name or normalized_name in queued_names:
                continue
            queued_names.add(normalized_name)
            # Resolve to see if already exists
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
                    vault_pending_writes.append(promoted)
                continue
            # Determine entity type: default to npc; later phases may infer from context
            entity_type = "npc"
            # Prepare minimal draft for NPC — required fields: species, role, status, disposition_to_pc
            draft: dict[str, object] = {
                "name": entity_name,
                "type": entity_type,
                "species": "unknown",
                "role": "unknown",
                "status": "alive",
                "disposition_to_pc": "neutral",
            }
            if entity_name.startswith("npc_"):
                draft["id"] = entity_name
            # Visibility: if entity is present in scene, it's player_known (they see it)
            visibility = "player_known"
            try:
                result = vault_page_upsert(
                    vault_service=vault_service,
                    entity_draft=draft,
                    visibility=visibility,
                    session_number=session_number,
                )
                vault_pending_writes.append(result.page)
            except ValueError:
                pass

    rolling_summary = _maybe_update_rolling_summary(
        state=state,
        services=services,
        scene_brief=scene_brief,
    )

    # Build rolling summary meta page if provided
    if vault_service is not None and isinstance(rolling_summary, str):
        # Use a fixed id; if conflict, slugify the summary title? Use "rolling_summary" as id; collides rarely
        frontmatter = LoreFrontmatter(
            id="rolling_summary",
            type="lore",
            name="Rolling Summary",
            aliases=[],
            visibility="gm_only",
            first_encountered=str(session_number),
            category="rolling_summary",
        )
        page = VaultPage(frontmatter, rolling_summary)
        vault_pending_writes.append(page)

    if vault_pending_writes:
        vault_pending_writes = _promote_pending_pages(
            vault_pending_writes,
            context={
                "scene_brief": scene_brief,
                "player_input": state.get("pending_player_input"),
                "pending_narration": state.get("pending_narration", []),
            },
        )

    player_input = state.get("pending_player_input")
    pending_conflicts = detect_conflicts(
        player_input if isinstance(player_input, str) else "",
        vault_pending_writes,
    )

    memory_packet = assemble_memory_packet(
        {**state, "rolling_summary": rolling_summary},
        conn=getattr(services, "transcript_conn", None),
        vault_service=vault_service,
    )

    # Serialize vault_pending_writes to a checkpoint-safe representation.
    # LangGraph's msgpack serializer cannot handle VaultPage objects directly.
    # The runtime will reconstruct VaultPage instances after the graph completes.
    if getattr(services, "transcript_conn", None) is None:
        pending_vault_payload: list[VaultPage] | list[dict[str, Any]] = vault_pending_writes
    else:
        pending_vault_payload = [
            {"frontmatter": page.frontmatter.model_dump(mode="json"), "body": page.body}
            for page in vault_pending_writes
        ]

    return {
        "session_state": session_state,
        "rolling_summary": rolling_summary,
        "pending_conflicts": pending_conflicts,
        "pending_player_input": None,
        "memory_packet": memory_packet.model_dump(),
        "vault_pending_writes": pending_vault_payload,
        # Phase 4: pending_narration preserved so smoke test can sync to TUI.
        # Phase 7 archivist will persist to transcript_entries before clearing.
        "pending_narration": state.get("pending_narration", []),
    }


def _resolve_known_entity(vault_service: VaultService, entity_name: str) -> VaultPage | None:
    """Resolve a scene entity across all supported types."""
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
    """Return a visibility-promoted copy of page, or None if no change needed.

    Callers must add the returned page to vault_pending_writes so promotion
    lands inside the transactional close_turn boundary.
    """
    new_visibility = promote_visibility(page, context)
    if new_visibility == page.frontmatter.visibility:
        return None
    return VaultPage(page.frontmatter.model_copy(update={"visibility": new_visibility}), page.body)


def _maybe_update_rolling_summary(
    *,
    state: dict[str, Any],
    services: Any,
    scene_brief: dict[str, Any],
) -> Any:
    old_summary = state.get("rolling_summary")
    llm_client = getattr(services, "llm", None)
    needs_initial_summary = not isinstance(old_summary, str) or not old_summary.strip()
    if llm_client is None or (
        not needs_initial_summary and not _is_scene_boundary(state=state, scene_brief=scene_brief)
    ):
        return old_summary
    snippets = _summary_snippets(state)
    if not snippets and not scene_brief:
        return old_summary
    summary = update_summary(
        old_summary=old_summary if isinstance(old_summary, str) else None,
        new_transcript_snippets=snippets,
        scene_brief=scene_brief,
        llm_client=llm_client,
        token_cap=800,
    )
    return summary


def _is_scene_boundary(*, state: dict[str, Any], scene_brief: dict[str, Any]) -> bool:
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
            {value for value in resolved if isinstance(value, str)}
            if isinstance(resolved, list)
            else set()
        )
        return all(isinstance(value, str) and value in resolved_set for value in beat_ids)
    beats = scene_brief.get("beats")
    resolved_beats = state.get("resolved_beats", [])
    if isinstance(beats, list) and beats:
        resolved_set = (
            {value for value in resolved_beats if isinstance(value, str)}
            if isinstance(resolved_beats, list)
            else set()
        )
        return all(isinstance(value, str) and value in resolved_set for value in beats)
    return False


def _summary_snippets(state: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    player_input = state.get("pending_player_input")
    if isinstance(player_input, str) and player_input.strip():
        snippets.append(f"Player: {player_input.strip()}")
    pending_narration = state.get("pending_narration", [])
    if isinstance(pending_narration, list):
        snippets.extend(
            value.strip() for value in pending_narration if isinstance(value, str) and value.strip()
        )
    return snippets
