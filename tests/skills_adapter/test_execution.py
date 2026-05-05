"""Tests for AgentSkillExecution runtime behavior."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sagasmith.skills_adapter import AgentSkillExecution, SkillNotFoundError, UnauthorizedSkillError
from sagasmith.skills_adapter.store import SkillStore

FIXTURES = Path(__file__).with_name("fixtures")
AGENTS_ROOT = FIXTURES / "agents"
SHARED_ROOT = FIXTURES / "skills"


@pytest.fixture
def store() -> SkillStore:
    skill_store = SkillStore(roots=[AGENTS_ROOT, SHARED_ROOT])
    skill_store.scan()
    return skill_store


def test_authorized_load_returns_instructions(store: SkillStore) -> None:
    execution = AgentSkillExecution("oracle", store)

    loaded = execution.load("valid-skill")

    assert loaded is not None
    assert loaded.record.name == "valid-skill"
    assert "Body content." in loaded.body


def test_load_distinguishes_unauthorized_and_not_found(store: SkillStore) -> None:
    execution = AgentSkillExecution("rules_lawyer", store)

    with pytest.raises(UnauthorizedSkillError):
        execution.load("valid-skill")

    with pytest.raises(SkillNotFoundError):
        execution.load("missing-skill")


def test_activate_records_unique_names_in_order(store: SkillStore) -> None:
    execution = AgentSkillExecution("oracle", store)

    execution.activate("valid-skill")
    execution.activate("shared-skill")
    execution.activate("valid-skill")

    assert execution.activated_names == ("valid-skill", "shared-skill")


def test_run_invokes_implementation_once_and_returns_value(store: SkillStore) -> None:
    execution = AgentSkillExecution("oracle", store)
    calls: list[str] = []

    def implementation(value: str) -> str:
        calls.append(value)
        return value.upper()

    result = execution.run("valid-skill", implementation, "ok")

    assert result == "OK"
    assert calls == ["ok"]
    assert execution.activated_names == ("valid-skill",)


def test_run_preserves_implementation_exceptions(store: SkillStore) -> None:
    execution = AgentSkillExecution("oracle", store)

    def implementation() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        execution.run("valid-skill", implementation)

    assert execution.activated_names == ("valid-skill",)


def test_none_store_mode_does_not_record_or_crash() -> None:
    execution = AgentSkillExecution("oracle", None)

    assert execution.load("valid-skill") is None
    assert execution.activate("valid-skill") is None
    assert execution.run("valid-skill", lambda: "ran") == "ran"
    assert execution.activated_names == ()


def test_shared_star_skill_can_be_activated_by_any_agent(store: SkillStore) -> None:
    execution = AgentSkillExecution("rules_lawyer", store)

    execution.activate("shared-skill")

    assert execution.activated_names == ("shared-skill",)


def test_catalog_text_renders_compact_catalog(store: SkillStore) -> None:
    execution = AgentSkillExecution("oracle", store)

    rendered = execution.catalog_text()

    assert "valid-skill" in rendered
    assert "shared-skill" in rendered
    assert not rendered.endswith("\n")


def test_skill_store_import_remains_lightweight() -> None:
    code = (
        "import sys\n"
        "from sagasmith.skills_adapter.store import SkillStore\n"
        "forbidden = {'textual', 'langgraph', 'sqlite3', 'httpx'}\n"
        "loaded = forbidden & set(sys.modules.keys())\n"
        "assert not loaded, f'heavy deps loaded: {loaded}'\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_run_unauthorized_skill_skips_activation_but_runs_implementation(
    store: SkillStore,
) -> None:
    """Unauthorized run() skips activation recording but still invokes the implementation."""
    execution = AgentSkillExecution("rules_lawyer", store)
    calls: list[str] = []

    def implementation(value: str) -> str:
        calls.append(value)
        return value.upper()

    # Does not raise; gracefully skips activation.
    result = execution.run("valid-skill", implementation, "ran-anyway")

    assert result == "RAN-ANYWAY"
    assert calls == ["ran-anyway"]
    # No activation recorded because skill was not authorized.
    assert execution.activated_names == ()


def test_run_missing_skill_skips_activation_but_runs_implementation(
    store: SkillStore,
) -> None:
    """Missing skill run() skips activation recording but still invokes the implementation."""
    execution = AgentSkillExecution("oracle", store)
    calls: list[str] = []

    def implementation(value: str) -> str:
        calls.append(value)
        return value.upper()

    # Does not raise; gracefully skips activation.
    result = execution.run("nonexistent-skill", implementation, "ran-anyway")

    assert result == "RAN-ANYWAY"
    assert calls == ["ran-anyway"]
    assert execution.activated_names == ()


def test_run_without_store_invokes_implementation() -> None:
    """When no store is configured, run() should invoke the implementation."""
    execution = AgentSkillExecution("oracle", None)
    calls: list[str] = []

    def implementation(value: str) -> str:
        calls.append(value)
        return value.upper()

    result = execution.run("any-skill", implementation, "ok")

    assert result == "OK"
    assert calls == ["ok"]
