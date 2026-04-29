"""Archivist agent node."""

from __future__ import annotations

from typing import Any

import yaml

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet,
)
from sagasmith.agents.archivist.skills.visibility_promotion.logic import promote_visibility
from sagasmith.agents.archivist.skills.vault_page_upsert.logic import (
    vault_page_upsert,
)
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.world import WorldBible
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter


def archivist_node(state: dict[str, Any], services: Any) -> dict[str, Any]:
    """Assemble memory packet, persist entity pages to vault, and return vault writes."""
    if services._call_recorder is not None:
        services._call_recorder.append("archivist")
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None:
            for skill_name in [
                "entity-resolution",
                "vault-page-upsert",
                "memory-packet-assembly",
                "visibility-promotion",
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
            body = yaml.safe_dump(
                world_bible.model_dump(mode="json"), sort_keys=False, allow_unicode=True
            )
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
            body = yaml.safe_dump(
                campaign_seed.model_dump(mode="json"), sort_keys=False, allow_unicode=True
            )
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
                _promote_existing_page(
                    vault_service=vault_service,
                    page=resolved,
                    context={
                        "scene_brief": scene_brief,
                        "player_input": state.get("pending_player_input"),
                        "pending_narration": state.get("pending_narration", []),
                    },
                )
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

    # Build rolling summary meta page if provided
    rolling_summary = state.get("rolling_summary")
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

    memory_packet = assemble_memory_packet(
        state,
        conn=getattr(services, "transcript_conn", None),
        vault_service=vault_service,
    )
    return {
        "session_state": session_state,
        "pending_player_input": None,
        "memory_packet": memory_packet.model_dump(),
        "vault_pending_writes": vault_pending_writes,
        # Phase 4: pending_narration preserved so smoke test can sync to TUI.
        # Phase 7 archivist will persist to transcript_entries before clearing.
        "pending_narration": state.get("pending_narration", []),
    }


def _resolve_known_entity(vault_service: VaultService, entity_name: str) -> VaultPage | None:
    """Resolve a scene entity without requiring aliases to exist."""
    for entity_type in ("npc", "location", "faction", "item", "quest", "callback", "lore"):
        resolved = vault_service.resolver.resolve(entity_name, entity_type=entity_type)
        if resolved is not None:
            return resolved
    return vault_service.resolver.resolve(entity_name, entity_type=None)


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


def _promote_existing_page(
    *, vault_service: VaultService, page: VaultPage, context: dict[str, Any]
) -> None:
    new_visibility = promote_visibility(page, context)
    if new_visibility == page.frontmatter.visibility:
        return
    promoted = VaultPage(page.frontmatter.model_copy(update={"visibility": new_visibility}), page.body)
    relative_path = _vault_relative_path(promoted)
    vault_service.write_page(promoted, relative_path)


def _vault_relative_path(page: VaultPage) -> Any:
    from pathlib import Path

    folder_by_type = {
        "npc": "npcs",
        "location": "locations",
        "faction": "factions",
        "item": "items",
        "quest": "quests",
        "callback": "callbacks",
        "session": "sessions",
        "lore": "lore",
    }
    folder = folder_by_type.get(page.frontmatter.type, "lore")
    return Path(folder) / f"{page.frontmatter.id}.md"
