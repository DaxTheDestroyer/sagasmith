"""Tests for load_skill authorization and not-found behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.skills_adapter.errors import SkillNotFoundError, UnauthorizedSkillError
from sagasmith.skills_adapter.loader import load_skill
from sagasmith.skills_adapter.store import SkillStore

FIXTURES = Path(__file__).with_name("fixtures")
AGENTS_ROOT = FIXTURES / "agents"
SHARED_ROOT = FIXTURES / "skills"


class TestLoadSkill:
    def test_loads_valid_skill(self):
        store = SkillStore(roots=[AGENTS_ROOT, SHARED_ROOT])
        store.scan()
        loaded = load_skill(store, "valid-skill", agent_name="oracle")
        assert loaded.record.name == "valid-skill"
        assert "Body content." in loaded.body

    def test_unauthorized_agent_raises(self):
        store = SkillStore(roots=[AGENTS_ROOT, SHARED_ROOT])
        store.scan()
        with pytest.raises(UnauthorizedSkillError):
            load_skill(store, "valid-skill", agent_name="archivist")

    def test_shared_skill_available_to_any_agent(self):
        store = SkillStore(roots=[AGENTS_ROOT, SHARED_ROOT])
        store.scan()
        loaded = load_skill(store, "shared-skill", agent_name="archivist")
        assert loaded.record.name == "shared-skill"

    def test_not_found_raises(self):
        store = SkillStore(roots=[AGENTS_ROOT, SHARED_ROOT])
        store.scan()
        with pytest.raises(SkillNotFoundError):
            load_skill(store, "does-not-exist", agent_name="oracle")
