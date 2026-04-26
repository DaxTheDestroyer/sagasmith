"""Compact SagaState reference invariant smoke tests."""

from __future__ import annotations

import json

import pytest

from sagasmith.evals.fixtures import make_valid_memory_packet
from sagasmith.schemas.common import MemoryEntityRef

pytestmark = pytest.mark.smoke

FORBIDDEN_INLINE_KEYS = {"transcript_body", "full_transcript", "vault_contents", "session_pages"}


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_walk_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_walk_keys(item))
        return keys
    return set()


def test_valid_fixture_json_size_is_bounded(valid_state_path):
    assert valid_state_path.stat().st_size < 20_000


def test_saga_state_json_has_no_inline_vault_fields(valid_state_path):
    data = json.loads(valid_state_path.read_text(encoding="utf-8"))
    assert FORBIDDEN_INLINE_KEYS.isdisjoint(_walk_keys(data))


def test_memory_packet_references_are_ids_not_bodies():
    packet = make_valid_memory_packet()
    entity_fields = set(MemoryEntityRef.model_fields)
    assert {"entity_id", "vault_path", "name"} <= entity_fields
    assert {"body", "content", "transcript_body", "vault_contents"}.isdisjoint(entity_fields)
    assert packet.entities[0].entity_id == "npc_marcus_innkeeper"
