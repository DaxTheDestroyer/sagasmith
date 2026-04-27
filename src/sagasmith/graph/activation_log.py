"""Per-node activation log with contextvar handoff for skill_name injection.

This module provides:
- `AgentActivationLogger`: context manager that writes one row to
  agent_skill_log per node invocation.
- `_current_activation` ContextVar: lets downstream nodes (Plan 04-05) call
  `get_current_activation().set_skill(name)` without re-plumbing.

Contextvar is single-threaded-safe. Phase 6+ parallel nodes must revisit.
"""

from __future__ import annotations

import re
import sqlite3
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.schemas.persistence import AgentSkillLogRecord
from sagasmith.services.errors import TrustServiceError

if TYPE_CHECKING:
    from sagasmith.evals.redaction import RedactionCanary

_SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

AgentName = Literal["onboarding", "oracle", "rules_lawyer", "orator", "archivist"]

_current_activation: ContextVar[AgentActivationLogger | None] = ContextVar(
    "_current_activation", default=None
)


def get_current_activation() -> AgentActivationLogger | None:
    return _current_activation.get()


@dataclass
class AgentActivation:
    turn_id: str
    agent_name: AgentName
    started_at: str
    skill_name: str | None = None


def _default_canary() -> RedactionCanary:
    # Mirror services/safety.py lazy factory pattern to avoid import cycles
    from sagasmith.evals.redaction import RedactionCanary

    return RedactionCanary()


class AgentActivationLogger:
    _conn: sqlite3.Connection
    _turn_id: str
    _agent_name: AgentName
    _activation: AgentActivation | None
    _canary: RedactionCanary | None
    _token: Token[AgentActivationLogger | None] | None

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        turn_id: str,
        agent_name: AgentName,
        canary: RedactionCanary | None = None,
    ) -> None:
        self._conn = conn
        self._turn_id = turn_id
        self._agent_name = agent_name
        self._activation: AgentActivation | None = None
        self._canary = canary  # lazy; _default_canary() if None
        self._token = None

    def set_skill(self, name: str) -> None:
        if not _SKILL_NAME_RE.match(name):
            raise ValueError(f"skill_name must match {_SKILL_NAME_RE.pattern}: got {name!r}")
        if self._activation is None:
            raise RuntimeError("set_skill called outside context manager")
        self._activation.skill_name = name

    def __enter__(self) -> AgentActivationLogger:
        self._activation = AgentActivation(
            turn_id=self._turn_id,
            agent_name=self._agent_name,
            started_at=datetime.now(UTC).isoformat(),
        )
        self._token = _current_activation.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> Literal[False]:
        try:
            completed_at = datetime.now(UTC).isoformat()
            if exc_type is None:
                outcome: Literal["success", "interrupted", "error"] = "success"
            else:
                # Detect LangGraph Interrupt (may be GraphInterrupt or similar)
                # Name is module-qualified; use a robust match
                exc_module = getattr(exc_type, "__module__", "")
                exc_name = getattr(exc_type, "__name__", "")
                if exc_module.startswith("langgraph") and "interrupt" in exc_name.lower():
                    outcome = "interrupted"
                else:
                    outcome = "error"

            assert self._activation is not None
            record = AgentSkillLogRecord(
                turn_id=self._activation.turn_id,
                agent_name=self._activation.agent_name,
                skill_name=self._activation.skill_name,
                started_at=self._activation.started_at,
                completed_at=completed_at,
                outcome=outcome,
            )
            canary = self._canary or _default_canary()
            if canary.scan(record.model_dump_json()):
                raise TrustServiceError("agent activation record contains redacted content")
            AgentSkillLogRepository(self._conn).append(record)
            # Do NOT commit — caller owns the transaction.
        finally:
            if self._token is not None:
                _current_activation.reset(self._token)
                self._token = None
            self._activation = None
        return False  # re-raise any original exception
