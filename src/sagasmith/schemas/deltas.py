"""Replayable state delta and canon conflict schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import SchemaModel


class StateDelta(SchemaModel):
    """Serializable state mutation with explicit authority source and reason."""

    id: str
    source: Literal["rules", "oracle", "archivist", "safety", "user"]
    path: str
    operation: Literal["set", "increment", "append", "remove"]
    value: Any = Field(description="opaque payload; deterministic service owns interpretation")
    reason: str


class CanonConflict(SchemaModel):
    """Canon conflict surfaced rather than silently overwritten."""

    id: str
    entity_id: str
    asserted_fact: str
    canonical_fact: str
    category: Literal["retcon_intent", "pc_misbelief", "narrator_error"]
    severity: Literal["minor", "major"]
    recommended_resolution: str
