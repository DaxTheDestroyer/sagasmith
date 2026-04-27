"""Tests for SkillCatalog and render_catalog_for_prompt."""

from __future__ import annotations

from pathlib import Path

from sagasmith.skills_adapter.catalog import SkillCatalog, render_catalog_for_prompt
from sagasmith.skills_adapter.store import SkillStore

FIXTURES = Path(__file__).with_name("fixtures")
ORACLE_SKILLS = FIXTURES / "agents" / "oracle" / "skills"
SHARED_SKILLS = FIXTURES / "skills"


class TestCatalog:
    def test_for_agent_returns_sorted_tuples(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        catalog = SkillCatalog.for_agent(store, "oracle")
        names = [name for name, _desc in catalog.entries]
        assert names == sorted(names)
        assert "valid-skill" in names
        assert "shared-skill" in names

    def test_description_length_cap(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        catalog = SkillCatalog.for_agent(store, "oracle")
        for _name, desc in catalog.entries:
            assert len(desc) <= 256

    def test_render_catalog_for_prompt(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        catalog = SkillCatalog.for_agent(store, "oracle")
        rendered = render_catalog_for_prompt(catalog)
        lines = rendered.split("\n")
        assert all(line.startswith("- ") for line in lines)
        assert "valid-skill" in rendered
        assert "shared-skill" in rendered
        # No trailing newline
        assert not rendered.endswith("\n")
