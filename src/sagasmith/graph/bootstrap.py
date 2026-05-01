"""Graph bootstrap: assemble agent nodes and compiled graph from services."""

from __future__ import annotations

import functools
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService

if TYPE_CHECKING:
    from sagasmith.schemas.provider import ProviderConfig
    from sagasmith.services.safety import SafetyEventService
    from sagasmith.skills_adapter.store import SkillStore


@dataclass(frozen=True)
class AgentServices:
    """Runtime services bundle injected into every agent node."""

    dice: DiceService
    cost: CostGovernor
    safety: SafetyEventService | None = None
    llm: object | None = None
    provider_config: ProviderConfig | None = None
    skill_store: SkillStore | None = None
    transcript_conn: sqlite3.Connection | None = None
    vault_service: object | None = None
    # test-only hook: if non-None, nodes append their name to this list on entry.
    # Used by graph tests to verify execution order without polluting production code.
    _call_recorder: list[str] | None = None


@dataclass(frozen=True)
class GraphBootstrap:
    """Holds bound node callables and the services bundle."""

    services: AgentServices
    onboarding: object
    oracle: object
    rules_lawyer: object
    orator: object
    archivist: object

    @classmethod
    def from_services(
        cls,
        *,
        dice: DiceService,
        cost: CostGovernor,
        safety: SafetyEventService | None = None,
        llm: object | None = None,
        provider_config: ProviderConfig | None = None,
        skill_store: SkillStore | None = None,
        transcript_conn: sqlite3.Connection | None = None,
        vault_service: object | None = None,
        _call_recorder: list[str] | None = None,
    ) -> GraphBootstrap:
        # Lazy default: only build a SkillStore when None is explicitly passed
        # and the caller hasn't already provided one. Tests that pass an empty
        # store bypass validation; production gets the production scan.
        if skill_store is None:
            skill_store = _default_skill_store()
        services = AgentServices(
            dice=dice,
            cost=cost,
            safety=safety,
            llm=llm,
            provider_config=provider_config,
            skill_store=skill_store,
            transcript_conn=transcript_conn,
            vault_service=vault_service,
            _call_recorder=_call_recorder,
        )
        from sagasmith.agents.archivist.node import archivist_node
        from sagasmith.agents.onboarding.node import onboarding_node
        from sagasmith.agents.oracle.node import oracle_node
        from sagasmith.agents.orator.node import orator_node
        from sagasmith.agents.rules_lawyer.node import rules_lawyer_node

        return cls(
            services=services,
            onboarding=functools.partial(onboarding_node, services=services),
            oracle=functools.partial(oracle_node, services=services),
            rules_lawyer=functools.partial(rules_lawyer_node, services=services),
            orator=functools.partial(orator_node, services=services),
            archivist=functools.partial(archivist_node, services=services),
        )


def _default_skill_store(*, first_slice_only: bool = False) -> SkillStore:
    """Return a SkillStore scanning the production skill roots.

    Raises SkillValidationError at construction if any SKILL.md has errors.
    """
    import sagasmith
    from sagasmith.skills_adapter import SkillStore
    from sagasmith.skills_adapter.errors import SkillValidationError

    pkg_root = Path(sagasmith.__file__).parent
    roots = [pkg_root / "agents", pkg_root / "skills"]
    store = SkillStore(roots=roots, first_slice_only=first_slice_only)
    store.scan()
    if store.errors:
        error_list = "\n".join(f"  - {p}: {msg}" for p, msg in store.errors)
        raise SkillValidationError(f"Production SKILL.md scan found errors:\n{error_list}")
    return store


def default_skill_store(*, first_slice_only: bool = False) -> SkillStore:
    """Public wrapper for the production skill store scan."""
    return _default_skill_store(first_slice_only=first_slice_only)


def build_default_graph(bootstrap: GraphBootstrap) -> Any:
    """Return a compiled StateGraph from a bootstrap bundle."""
    from sagasmith.graph.graph import build_saga_graph

    return build_saga_graph(bootstrap)
