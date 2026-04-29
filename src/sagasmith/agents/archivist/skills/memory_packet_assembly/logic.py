"""Phase 7 MemoryPacket assembly with hybrid retrieval.

Retrieval pipeline:
1. Rolling summary from graph state (produced by rolling-summary-update)
2. Entity resolution via vault EntityResolver
3. FTS5 keyword search for scene-relevant vault pages
4. NetworkX graph neighborhood retrieval
5. Open callback query from vault
6. Recent transcript from SQLite
7. Token-bounded assembly with truncation
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from sagasmith.agents.archivist.entity_stubs import stub_entity_refs
from sagasmith.agents.archivist.transcript_context import (
    format_transcript_context,
    get_recent_transcript_context,
)
from sagasmith.schemas.common import MemoryEntityRef, estimate_tokens
from sagasmith.schemas.narrative import MemoryPacket

DEFAULT_MEMORY_TOKEN_CAP = 2048
RECENT_TRANSCRIPT_LIMIT = 8
FTS5_QUERY_LIMIT = 5
GRAPH_NEIGHBOR_DEPTH = 1
GRAPH_NEIGHBOR_MAX = 10
MAX_OPEN_CALLBACKS = 3

_FTS_QUERY_PATTERN = re.compile(r"[^\w\s]")


def assemble_memory_packet(
    state: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    vault_service: object | None = None,
    token_cap: int = DEFAULT_MEMORY_TOKEN_CAP,
) -> MemoryPacket:
    """Assemble a bounded MemoryPacket using hybrid retrieval from vault and transcript."""

    campaign_id = str(state.get("campaign_id", ""))
    scene_brief_raw = state.get("scene_brief") or {}
    scene_brief: dict[str, Any] = scene_brief_raw if isinstance(scene_brief_raw, dict) else {}

    session_state_raw = state.get("session_state") or {}
    session_state: dict[str, Any] = (
        session_state_raw if isinstance(session_state_raw, dict) else {}
    )
    current_session_raw = session_state.get("session_number", 1)
    current_session = current_session_raw if isinstance(current_session_raw, int) else 1
    turn_count_raw = session_state.get("turn_count", 0)
    turn_count = turn_count_raw if isinstance(turn_count_raw, int) else 0

    retrieval_notes: list[str] = []

    # --- 1. Rolling summary ---
    summary = state.get("rolling_summary") or ""
    if not isinstance(summary, str):
        summary = ""
    if summary:
        retrieval_notes.append("rolling_summary:included")
    else:
        summary = _build_fallback_summary(state, scene_brief=scene_brief, turn_count=turn_count)
        retrieval_notes.append("rolling_summary:fallback_generated")

    # --- 2. Recent transcript ---
    transcript_entries = get_recent_transcript_context(
        conn,
        campaign_id=campaign_id,
        limit=RECENT_TRANSCRIPT_LIMIT,
    )
    recent_turns = format_transcript_context(transcript_entries)
    if not recent_turns:
        recent_turns = _fallback_recent_context(state)
        retrieval_notes.append("transcript:fallback_state_context")
    else:
        retrieval_notes.append(f"transcript:{len(recent_turns)}_entries")

    # --- 3. Entity resolution ---
    entities, resolved_entity_ids = _resolve_entities(
        scene_brief=scene_brief,
        vault_service=vault_service,
        recent_turns=recent_turns,
    )

    # --- 4. FTS5 keyword search ---
    fts5_paths: list[str] = []
    if conn is not None:
        fts5_paths = _fts5_search(
            conn=conn,
            scene_brief=scene_brief,
            resolved_entity_ids=resolved_entity_ids,
        )
        if fts5_paths:
            retrieval_notes.append(f"fts5:{len(fts5_paths)}_matches")
        else:
            retrieval_notes.append("fts5:no_matches")

    # --- 5. NetworkX graph neighbors ---
    graph_neighbor_ids: list[str] = []
    if resolved_entity_ids:
        graph_neighbor_ids = _graph_neighbors(
            resolved_entity_ids=resolved_entity_ids,
        )
        if graph_neighbor_ids:
            retrieval_notes.append(f"graph:{len(graph_neighbor_ids)}_neighbors")

    # Merge graph neighbors into entities as context refs
    _add_graph_neighbor_refs(
        entities=entities,
        neighbor_ids=graph_neighbor_ids,
        known_ids={e.entity_id for e in entities},
    )

    # --- 6. Open callbacks ---
    open_callbacks = _find_open_callbacks(
        vault_service=vault_service,
        current_session=current_session,
    )
    if open_callbacks:
        retrieval_notes.append(f"callbacks:{len(open_callbacks)}_open")

    # --- 7. Token cap enforcement ---
    bounded_summary, bounded_turns = _enforce_cap(
        summary,
        recent_turns,
        token_cap=token_cap,
    )

    return MemoryPacket(
        token_cap=token_cap,
        summary=bounded_summary,
        entities=entities,
        recent_turns=bounded_turns,
        open_callbacks=open_callbacks,
        retrieval_notes=retrieval_notes,
    )


def assemble_memory_packet_stub(
    state: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    token_cap: int = DEFAULT_MEMORY_TOKEN_CAP,
) -> MemoryPacket:
    """Phase 6 stub preserved for backward compatibility.

    Delegates to the full assembly when no vault_service is available.
    """
    return assemble_memory_packet(
        state,
        conn=conn,
        vault_service=None,
        token_cap=token_cap,
    )


# ---------------------------------------------------------------------------
# Entity resolution helpers
# ---------------------------------------------------------------------------


def _resolve_entities(
    *,
    scene_brief: dict[str, Any],
    vault_service: object | None,
    recent_turns: list[str],
) -> tuple[list[MemoryEntityRef], list[str]]:
    """Resolve present entities to MemoryEntityRefs with vault paths."""
    location = scene_brief.get("location") if isinstance(scene_brief.get("location"), str) else None
    present_entities = [
        value for value in scene_brief.get("present_entities", []) if isinstance(value, str)
    ]

    entities: list[MemoryEntityRef] = []
    resolved_ids: list[str] = []
    resolver = getattr(vault_service, "resolver", None) if vault_service is not None else None

    if resolver is not None:
        if location:
            page = resolver.resolve(location, entity_type="location")
            if page is not None:
                ref = _page_to_entity_ref(page, kind="location")
                entities.append(ref)
                resolved_ids.append(ref.entity_id)
            else:
                entities.append(
                    MemoryEntityRef(
                        entity_id=f"location_{_slugify(location)}",
                        kind="location",
                        name=location,
                        vault_path=None,
                        provisional=True,
                    )
                )

        for entity_name in present_entities:
            matched = False
            for entity_type in ("npc", "location", "faction", "item"):
                page = resolver.resolve(entity_name, entity_type=entity_type)
                if page is not None:
                    ref = _page_to_entity_ref(page, kind=entity_type)
                    if ref.entity_id not in {e.entity_id for e in entities}:
                        entities.append(ref)
                        resolved_ids.append(ref.entity_id)
                    matched = True
                    break
            if not matched:
                entities.append(
                    MemoryEntityRef(
                        entity_id=f"npc_{_slugify(entity_name)}",
                        kind="npc",
                        name=entity_name,
                        vault_path=None,
                        provisional=True,
                    )
                )
    else:
        entities = stub_entity_refs(
            location=location,
            present_entities=present_entities,
            recent_turns=recent_turns,
        )

    return entities, resolved_ids


def _page_to_entity_ref(page: object, *, kind: str) -> MemoryEntityRef:
    """Convert a VaultPage to a MemoryEntityRef."""
    from sagasmith.vault.page import VaultPage

    if isinstance(page, VaultPage):
        fm = page.frontmatter
        vault_path = f"{_type_to_subfolder(fm.type)}/{fm.id}.md"
        return MemoryEntityRef(
            entity_id=fm.id,
            kind=kind,
            name=fm.name,
            vault_path=vault_path,
            provisional=False,
        )
    return MemoryEntityRef(
        entity_id=f"{kind}_unknown",
        kind=kind,
        name="Unknown",
        vault_path=None,
        provisional=True,
    )


def _type_to_subfolder(page_type: str) -> str:
    mapping = {
        "npc": "npcs",
        "location": "locations",
        "faction": "factions",
        "item": "items",
        "quest": "quests",
        "callback": "callbacks",
        "session": "sessions",
        "lore": "lore",
    }
    return mapping.get(page_type, "lore")


# ---------------------------------------------------------------------------
# FTS5 search helpers
# ---------------------------------------------------------------------------


def _fts5_search(
    *,
    conn: sqlite3.Connection,
    scene_brief: dict[str, Any],
    resolved_entity_ids: list[str],
) -> list[str]:
    """Run FTS5 queries based on scene context. Returns matching vault_paths."""
    from sagasmith.memory.fts5 import FTS5Index

    fts = FTS5Index(conn)
    search_terms = _build_fts_terms(scene_brief=scene_brief, entity_ids=resolved_entity_ids)
    seen: set[str] = set()
    paths: list[str] = []
    for term in search_terms:
        for vault_path, _score in fts.query(term, limit=FTS5_QUERY_LIMIT):
            if vault_path not in seen:
                seen.add(vault_path)
                paths.append(vault_path)
            if len(paths) >= FTS5_QUERY_LIMIT:
                break
        if len(paths) >= FTS5_QUERY_LIMIT:
            break
    return paths


def _build_fts_terms(
    *,
    scene_brief: dict[str, Any],
    entity_ids: list[str],
) -> list[str]:
    """Build FTS5 search terms from scene context."""
    terms: list[str] = []
    location = scene_brief.get("location")
    if isinstance(location, str) and location:
        clean = _sanitize_fts_term(location)
        if clean:
            terms.append(clean)
    for eid in entity_ids:
        parts = eid.split("_", 1)
        if len(parts) == 2:
            clean = _sanitize_fts_term(parts[1].replace("_", " "))
            if clean:
                terms.append(clean)
    return terms[:5]


def _sanitize_fts_term(text: str) -> str:
    """Clean text for safe FTS5 MATCH query usage."""
    cleaned = _FTS_QUERY_PATTERN.sub("", text).strip()
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) <= 1:
        return cleaned
    return " OR ".join(words)


# ---------------------------------------------------------------------------
# Graph neighbor helpers
# ---------------------------------------------------------------------------


def _graph_neighbors(
    *,
    resolved_entity_ids: list[str],
) -> list[str]:
    """Get graph neighbors for resolved entity IDs."""
    from sagasmith.memory.graph import get_vault_graph

    graph = get_vault_graph()
    all_neighbors: set[str] = set()
    for eid in resolved_entity_ids:
        neighbors = graph.get_neighbors(eid, depth=GRAPH_NEIGHBOR_DEPTH)
        all_neighbors.update(neighbors)
        if len(all_neighbors) >= GRAPH_NEIGHBOR_MAX:
            break
    return list(all_neighbors)[:GRAPH_NEIGHBOR_MAX]


def _add_graph_neighbor_refs(
    *,
    entities: list[MemoryEntityRef],
    neighbor_ids: list[str],
    known_ids: set[str],
) -> None:
    """Add graph neighbor entity refs to the entities list."""
    for nid in neighbor_ids:
        if nid in known_ids:
            continue
        kind = _infer_kind_from_id(nid)
        entities.append(
            MemoryEntityRef(
                entity_id=nid,
                kind=kind,
                name=nid.replace("_", " ").title(),
                vault_path=None,
                provisional=True,
            )
        )
        known_ids.add(nid)


def _infer_kind_from_id(entity_id: str) -> str:
    """Infer entity kind from an ID like 'npc_marcus' or 'loc_tavern'."""
    prefix_map = {
        "npc_": "npc",
        "loc_": "location",
        "fac_": "faction",
        "item_": "item",
        "quest_": "quest",
        "cb_": "callback",
        "session_": "session",
        "lore_": "lore",
    }
    for prefix, kind in prefix_map.items():
        if entity_id.startswith(prefix):
            return kind
    return "entity"


# ---------------------------------------------------------------------------
# Callback helpers
# ---------------------------------------------------------------------------


def _find_open_callbacks(
    *,
    vault_service: object | None,
    current_session: int,
) -> list[str]:
    """Find open callback IDs from the vault."""
    if vault_service is None:
        return []
    master_path = getattr(vault_service, "master_path", None)
    if master_path is None:
        return []

    callback_dir = Path(master_path) / "callbacks"
    if not callback_dir.exists():
        return []

    from sagasmith.vault.page import VaultPage

    open_cbs: list[str] = []
    for cb_file in callback_dir.glob("*.md"):
        try:
            page = VaultPage.load_file(cb_file)
            fm = page.frontmatter
            if fm.type != "callback":
                continue
            if getattr(fm, "status", "") != "open":
                continue
            seeded_in = getattr(fm, "seeded_in", None)
            if seeded_in is not None:
                try:
                    seeded_session = int(str(seeded_in).replace("session_", ""))
                    if seeded_session > current_session:
                        continue
                except (ValueError, TypeError):
                    pass
            open_cbs.append(fm.id)
            if len(open_cbs) >= MAX_OPEN_CALLBACKS:
                break
        except Exception:
            continue
    return open_cbs


# ---------------------------------------------------------------------------
# Summary and cap helpers
# ---------------------------------------------------------------------------


def _fallback_recent_context(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    pending_input = state.get("pending_player_input")
    if isinstance(pending_input, str) and pending_input:
        lines.append(f"current:player_input: {pending_input}")
    for index, line in enumerate(state.get("pending_narration", [])):
        if isinstance(line, str) and line:
            lines.append(f"current:{index}:narration_final: {line}")
    return lines


def _build_fallback_summary(
    state: dict[str, Any], *, scene_brief: dict[str, Any], turn_count: int
) -> str:
    intent = scene_brief.get("intent")
    location = scene_brief.get("location")
    parts = [f"Turn {turn_count}."]
    if isinstance(intent, str) and intent:
        parts.append(f"Scene intent: {intent}.")
    if isinstance(location, str) and location:
        parts.append(f"Location: {location}.")
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unknown"
