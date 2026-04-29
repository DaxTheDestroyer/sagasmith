"""Archivist agent node."""

from __future__ import annotations

import yaml

from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
    assemble_memory_packet_stub,
)
from sagasmith.agents.archivist.skills.vault_page_upsert.logic import (
    vault_page_upsert,
)
from sagasmith.graph.activation_log import get_current_activation
from sagasmith.schemas.world import WorldBible
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter


def archivist_node(state, services):
    """Assemble memory packet, persist entity pages to vault, and return vault writes."""
    if services._call_recorder is not None:
        services._call_recorder.append("archivist")
    activation = get_current_activation()
    if activation is not None:
        store = services.skill_store
        if store is not None:
            for skill_name in ["vault-page-upsert", "memory-packet-assembly", "entity-resolution"]:
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
            body = yaml.safe_dump(world_bible.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
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
            body = yaml.safe_dump(campaign_seed.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
            page = VaultPage(frontmatter, body)
            vault_pending_writes.append(page)

    # Process present entities from scene_brief: write new entity pages
    scene_brief = state.get("scene_brief") or {}
    present_entities = scene_brief.get("present_entities", [])
    if vault_service is not None and isinstance(present_entities, list):
        for entity_name in present_entities:
            if not isinstance(entity_name, str):
                continue
            # Resolve to see if already exists
            resolved = vault_service.resolver.resolve(entity_name, entity_type=None)
            if resolved is not None:
                # Already exists; skip writing (or could be updated later)
                continue
            # Determine entity type: default to npc; later phases may infer from context
            entity_type = "npc"
            # Prepare minimal draft for NPC — required fields: species, role, status, disposition_to_pc
            draft = {
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
                _path, _action = vault_page_upsert(
                    vault_service=vault_service,
                    entity_draft=draft,
                    visibility=visibility,
                    session_number=session_number,
                )
                page = vault_service.resolver.resolve(entity_name, entity_type)
                if page is not None:
                    vault_pending_writes.append(page)
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

    memory_packet = assemble_memory_packet_stub(
        state,
        conn=getattr(services, "transcript_conn", None),
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
