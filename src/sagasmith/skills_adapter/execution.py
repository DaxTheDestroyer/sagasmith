"""Agent Skills execution runtime.

This Module binds one SagaSmith agent to the Agent Skills runtime rules:
catalog rendering, authorization, instruction loading, duplicate-suppressed
activation recording, and Python Implementation invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from sagasmith.skills_adapter.catalog import SkillCatalog, render_catalog_for_prompt
from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError
from sagasmith.skills_adapter.loader import LoadedSkill, load_skill

if TYPE_CHECKING:
    from collections.abc import Callable

    from sagasmith.skills_adapter.store import SkillStore

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class AgentSkillExecution:
    """Runtime Agent Skills Interface bound to one agent turn."""

    agent_name: str
    store: SkillStore | None
    _activated: list[str] = field(default_factory=list)

    @property
    def activated_names(self) -> tuple[str, ...]:
        """Return skill names activated through this execution object."""

        return tuple(self._activated)

    def catalog(self) -> SkillCatalog:
        """Return the compact per-agent skill catalog."""

        if self.store is None:
            return SkillCatalog(entries=())
        return SkillCatalog.for_agent(self.store, self.agent_name)

    def catalog_text(self) -> str:
        """Render the compact skill catalog for prompt injection."""

        return render_catalog_for_prompt(self.catalog())

    def load(self, skill_name: str) -> LoadedSkill | None:
        """Authorize and load full skill instructions for this agent."""

        if self.store is None:
            return None
        return load_skill(self.store, skill_name, agent_name=self.agent_name)

    def activate(self, skill_name: str) -> LoadedSkill | None:
        """Load and record a skill activation when authorized.

        Missing or unauthorized skills are treated as unavailable capabilities,
        preserving the existing provider-free and partial-store test behavior.
        """

        try:
            loaded = self.load(skill_name)
        except (SkillNotFoundError, UnauthorizedSkillError):
            return None
        if loaded is None:
            return None
        if skill_name not in self._activated:
            self._activated.append(skill_name)
            self._set_graph_activation(skill_name)
        return loaded

    def run(
        self,
        skill_name: str,
        implementation: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Activate a skill and invoke its Python Implementation.

        When a SkillStore is configured, the skill is validated via load_skill.
        If the skill is not found or not authorized for this agent, activation
        is skipped (no activation is recorded) but the implementation is still
        invoked. This preserves graceful degradation for provider-free tests
        and partial skill stores. When no store is configured, the implementation
        runs without any authorization attempt.
        """

        if self.store is not None:
            try:
                load_skill(self.store, skill_name, agent_name=self.agent_name)
            except (SkillNotFoundError, UnauthorizedSkillError):
                # Skill not available: still run implementation without recording.
                return implementation(*args, **kwargs)
        self.activate(skill_name)
        return implementation(*args, **kwargs)

    def _set_graph_activation(self, skill_name: str) -> None:
        from sagasmith.graph.activation_log import get_current_activation

        activation = get_current_activation()
        if activation is not None:
            activation.set_skill(skill_name)
