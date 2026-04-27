"""Deterministic JSON Schema exporter for persisted and LLM-boundary models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .campaign import CampaignManifest, ProviderSettings
from .deltas import CanonConflict, StateDelta
from .mechanics import CharacterSheet, CheckProposal, CheckResult, CombatState, RollResult
from .narrative import MemoryPacket, SceneBrief, SessionState
from .persistence import (
    CheckpointRef,
    CostLogRecord,
    StateDeltaRecord,
    TranscriptEntry,
    TurnRecord,
)
from .player import ContentPolicy, HouseRules, PlayerProfile
from .provider import (
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderLogRecord,
)
from .safety_cost import CostState, SafetyEvent
from .saga_state import SagaState

type SchemaModelClass = type[BaseModel]

LLM_BOUNDARY_AND_PERSISTED_MODELS: list[SchemaModelClass] = [
    CampaignManifest,
    ProviderSettings,
    SagaState,
    PlayerProfile,
    ContentPolicy,
    HouseRules,
    SessionState,
    SceneBrief,
    MemoryPacket,
    CharacterSheet,
    CombatState,
    CheckProposal,
    CheckResult,
    RollResult,
    StateDelta,
    CanonConflict,
    SafetyEvent,
    CostState,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderLogRecord,
    CostLogRecord,
    TurnRecord,
    CheckpointRef,
    TranscriptEntry,
    StateDeltaRecord,
]


def export_all_schemas(out_dir: Path) -> list[Path]:
    """Write one deterministic JSON Schema file per exported model."""

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in sorted(
        LLM_BOUNDARY_AND_PERSISTED_MODELS, key=lambda model_class: model_class.__name__
    ):
        schema = model.model_json_schema()
        path = out_dir / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return sorted(written, key=lambda p: p.name)
