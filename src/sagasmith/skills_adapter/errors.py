"""Skill adapter error hierarchy."""

from __future__ import annotations


class SkillAdapterError(Exception):
    """Base class for all skill adapter errors."""


class SkillValidationError(SkillAdapterError):
    """A SKILL.md file failed validation (frontmatter, name, authorization, redaction)."""


class SkillNotFoundError(SkillAdapterError):
    """The requested skill does not exist for the specified agent."""


class UnauthorizedSkillError(SkillAdapterError):
    """The agent is not authorized to load this skill."""


class FrontmatterError(SkillValidationError):
    """The SKILL.md frontmatter block could not be parsed or violates the supported subset."""
