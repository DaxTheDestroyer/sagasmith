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

from sagasmith.skills_adapter.errors import (
    FrontmatterError,
    SkillAdapterError,
    SkillNotFoundError,
    SkillValidationError,
    UnauthorizedSkillError,
)
from sagasmith.skills_adapter.frontmatter import SUPPORTED_SUBSET, parse_frontmatter

__all__ = [
    "SUPPORTED_SUBSET",
    "FrontmatterError",
    "SkillAdapterError",
    "SkillNotFoundError",
    "SkillValidationError",
    "UnauthorizedSkillError",
    "parse_frontmatter",
]
