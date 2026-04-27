"""SkillStore — filesystem discovery + frontmatter validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from sagasmith.skills_adapter.errors import FrontmatterError, SkillValidationError
from sagasmith.skills_adapter.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    pass

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_MAX_BODY_BYTES = 256 * 1024

ImplementationSurface = Literal["deterministic", "prompted", "hybrid", "tool-call"]


class _Canary(Protocol):
    def scan(self, text: str) -> list[Any]: ...


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    agent_scope: str  # agent name or "_shared"
    allowed_agents: tuple[str, ...]  # ("*",) means any agent (cross-cutting only)
    implementation_surface: ImplementationSurface
    first_slice: bool
    success_signal: str | None
    body: str
    path: Path


@dataclass
class SkillStore:
    roots: list[Path]
    first_slice_only: bool = False
    skills: dict[str, list[SkillRecord]] = field(default_factory=dict)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    _canary: _Canary | None = None

    def scan(self) -> None:
        """Discover and validate every SKILL.md under self.roots."""
        if self._canary is None:
            from sagasmith.evals.redaction import RedactionCanary

            self._canary = RedactionCanary()
        self.skills.clear()
        self.errors.clear()
        self.skipped.clear()
        seen_names: dict[tuple[str, str], Path] = {}

        for root in self.roots:
            root = Path(root)
            if not root.exists():
                continue
            # Deterministic ordering — sorted() on rglob results
            for skill_md in sorted(root.rglob("SKILL.md")):
                try:
                    record = self._load_record(skill_md, root)
                except SkillValidationError as e:
                    self.errors.append((skill_md, str(e)))
                    continue

                key = (record.agent_scope, record.name)
                if key in seen_names:
                    self.errors.append(
                        (
                            skill_md,
                            f"duplicate name {record.name} under {record.agent_scope} (first: {seen_names[key]})",
                        )
                    )
                    continue
                seen_names[key] = skill_md

                if self.first_slice_only and not record.first_slice:
                    self.skipped.append((skill_md, "first_slice_only filter"))
                    continue

                self.skills.setdefault(record.agent_scope, []).append(record)

    def _load_record(self, path: Path, root: Path) -> SkillRecord:
        text = path.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > _MAX_BODY_BYTES:
            raise SkillValidationError(f"body exceeds {_MAX_BODY_BYTES // 1024}KB")
        try:
            fm, body = parse_frontmatter(text)
        except FrontmatterError as e:
            raise SkillValidationError(f"frontmatter: {e}") from e

        # Canary scan on body
        assert self._canary is not None
        if self._canary.scan(body):
            raise SkillValidationError("redacted content")

        # Determine agent_scope from path structure
        # root/<agent>/skills/<skill-name>/SKILL.md  → agent
        # root/<skill-name>/SKILL.md                  → _shared
        rel = path.relative_to(root).parts
        if len(rel) == 4 and rel[1] == "skills":
            agent_scope = rel[0]
        elif len(rel) == 2:
            agent_scope = "_shared"
        else:
            raise SkillValidationError(f"unexpected skill layout: {rel}")

        # Validate name
        name = fm.get("name")
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise SkillValidationError(f"invalid name: {name!r} (must match {_NAME_RE.pattern})")

        # Description
        description = fm.get("description")
        if not isinstance(description, str) or len(description) > 256:
            raise SkillValidationError("description missing or > 256 chars")

        # allowed_agents
        allowed_agents = fm.get("allowed_agents")
        if not isinstance(allowed_agents, list) or not all(isinstance(a, str) for a in allowed_agents):
            raise SkillValidationError("allowed_agents must be a list of strings")
        # REJECT agent-scoped skills with ["*"] — no silent downgrade
        if agent_scope != "_shared" and "*" in allowed_agents:
            raise SkillValidationError(
                f"agent-scoped skills must not declare allowed_agents: ['*'] "
                f"(found under agents/{agent_scope}/skills/)"
            )

        # implementation_surface
        impl = fm.get("implementation_surface")
        if impl not in ("deterministic", "prompted", "hybrid", "tool-call"):
            raise SkillValidationError(
                f"implementation_surface must be one of deterministic|prompted|hybrid|tool-call; got {impl!r}"
            )

        # first_slice (default True)
        first_slice = fm.get("first_slice", True)
        if not isinstance(first_slice, bool):
            raise SkillValidationError(f"first_slice must be bool; got {first_slice!r}")

        success_signal = fm.get("success_signal")
        if success_signal is not None and not isinstance(success_signal, str):
            raise SkillValidationError("success_signal must be string or absent")

        return SkillRecord(
            name=name,
            description=description,
            agent_scope=agent_scope,
            allowed_agents=tuple(allowed_agents),
            implementation_surface=impl,
            first_slice=first_slice,
            success_signal=success_signal,
            body=body,
            path=path,
        )

    def find(self, *, name: str, agent_scope: str) -> SkillRecord | None:
        for record in self.skills.get(agent_scope, []):
            if record.name == name:
                return record
        return None

    def list_for_agent(self, agent_name: str) -> list[SkillRecord]:
        """Return agent-scoped skills + shared skills that allow this agent."""
        result: list[SkillRecord] = list(self.skills.get(agent_name, []))
        for record in self.skills.get("_shared", []):
            if agent_name in record.allowed_agents or "*" in record.allowed_agents:
                result.append(record)
        return result
