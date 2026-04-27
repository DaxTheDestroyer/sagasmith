"""Agent Skills adapter package.

Provides filesystem discovery, YAML-lite frontmatter parsing,
compact skill catalogs, and on-demand skill loading for LangGraph nodes.

Modules:
    store       — SkillStore and SkillRecord
    catalog     — SkillCatalog and render_catalog_for_prompt
    loader      — load_skill and LoadedSkill
    errors      — SkillAdapterError hierarchy
    frontmatter — parse_frontmatter and SUPPORTED_SUBSET
"""

from __future__ import annotations

from sagasmith.skills_adapter.catalog import SkillCatalog, render_catalog_for_prompt
from sagasmith.skills_adapter.errors import (
    FrontmatterError,
    SkillAdapterError,
    SkillNotFoundError,
    SkillValidationError,
    UnauthorizedSkillError,
)
from sagasmith.skills_adapter.frontmatter import SUPPORTED_SUBSET, parse_frontmatter
from sagasmith.skills_adapter.loader import LoadedSkill, load_skill
from sagasmith.skills_adapter.store import SkillRecord, SkillStore

__all__ = [
    "SUPPORTED_SUBSET",
    "FrontmatterError",
    "LoadedSkill",
    "SkillAdapterError",
    "SkillCatalog",
    "SkillNotFoundError",
    "SkillRecord",
    "SkillStore",
    "SkillValidationError",
    "UnauthorizedSkillError",
    "load_skill",
    "parse_frontmatter",
    "render_catalog_for_prompt",
]
