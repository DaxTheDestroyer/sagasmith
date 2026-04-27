"""load_skill — on-demand skill loading with authorization."""

from __future__ import annotations

from dataclasses import dataclass

from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError
from sagasmith.skills_adapter.store import SkillRecord, SkillStore


@dataclass(frozen=True)
class LoadedSkill:
    record: SkillRecord
    body: str


def load_skill(store: SkillStore, name: str, *, agent_name: str) -> LoadedSkill:
    # Search the agent's own list first (authorized skills)
    for record in store.list_for_agent(agent_name):
        if record.name == name:
            return LoadedSkill(record=record, body=record.body)

    # If not in agent's list, search all scopes to distinguish
    # "not found" from "not authorized"
    for scope_records in store.skills.values():
        for record in scope_records:
            if record.name == name:
                raise UnauthorizedSkillError(f"{agent_name} not authorized for {name}")

    raise SkillNotFoundError(f"{name} not available for {agent_name}")
