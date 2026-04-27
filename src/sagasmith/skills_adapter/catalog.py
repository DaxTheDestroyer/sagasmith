"""SkillCatalog — per-agent (name, description) tuples for system-prompt injection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillCatalog:
    entries: tuple[tuple[str, str], ...]

    @classmethod
    def for_agent(cls, store, agent_name: str) -> SkillCatalog:
        records = store.list_for_agent(agent_name)
        pairs = tuple(sorted((r.name, r.description) for r in records))
        return cls(entries=pairs)


def render_catalog_for_prompt(catalog: SkillCatalog) -> str:
    return "\n".join(f"- {name} — {desc}" for name, desc in catalog.entries)
