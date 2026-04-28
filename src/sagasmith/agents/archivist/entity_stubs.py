"""Provisional entity reference stubs for Phase 6 memory packets."""

from __future__ import annotations

import re

from sagasmith.schemas.common import MemoryEntityRef

_ENTITY_WORDS = re.compile(r"\b[A-Z][a-zA-Z']{2,}(?:\s+[A-Z][a-zA-Z']{2,})?\b")
_STOP_NAMES = {
    "The",
    "You",
    "Your",
    "Phase",
    "MemoryPacket",
    "Oracle",
    "Orator",
    "Archivist",
}


def stub_entity_refs(
    *,
    location: str | None = None,
    present_entities: list[str] | None = None,
    recent_turns: list[str] | None = None,
) -> list[MemoryEntityRef]:
    """Build deterministic provisional entity refs from scene and transcript text."""

    refs: dict[str, MemoryEntityRef] = {}
    if location:
        _add_ref(refs, kind="location", name=location)
    for entity_name in present_entities or []:
        _add_ref(refs, kind="npc", name=entity_name)
    for line in recent_turns or []:
        for match in _ENTITY_WORDS.findall(line):
            name = match.strip()
            if name not in _STOP_NAMES:
                _add_ref(refs, kind="npc", name=name)
    return list(refs.values())


def _add_ref(refs: dict[str, MemoryEntityRef], *, kind: str, name: str) -> None:
    normalized_name = " ".join(name.split())
    if not normalized_name:
        return
    entity_id = f"{kind}_{_slugify(normalized_name)}"
    refs.setdefault(
        entity_id,
        MemoryEntityRef(
            entity_id=entity_id,
            kind=kind,
            name=normalized_name,
            vault_path=None,
            provisional=True,
        ),
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unknown"
