"""Tests for SkillStore scanning, validation, and deterministic ordering."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sagasmith.skills_adapter.errors import SkillValidationError
from sagasmith.skills_adapter.store import SkillRecord, SkillStore

FIXTURES = Path(__file__).with_name("fixtures")
ORACLE_SKILLS = FIXTURES / "agents" / "oracle" / "skills"
SHARED_SKILLS = FIXTURES / "skills"


class TestScan:
    def test_discovers_all_skills(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        oracle_records = {r.name for r in store.skills.get("oracle", [])}
        shared_records = {r.name for r in store.skills.get("_shared", [])}
        assert "valid-skill" in oracle_records
        assert "shared-skill" in shared_records

    def test_deterministic_path_sort(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        first = [r.path for r in store.skills.get("oracle", [])]
        store.scan()
        second = [r.path for r in store.skills.get("oracle", [])]
        assert first == second

    def test_lexicographic_order(self, tmp_path: Path):
        # Create files in non-lexicographic creation order
        root = tmp_path / "skills"
        (root / "c-skill" / "SKILL.md").parent.mkdir(parents=True)
        (root / "a-skill" / "SKILL.md").parent.mkdir(parents=True)
        (root / "b-skill" / "SKILL.md").parent.mkdir(parents=True)
        (root / "c-skill" / "SKILL.md").write_text("---\nname: c-skill\ndescription: c\nallowed_agents: [o]\nimplementation_surface: prompted\n---\n")
        (root / "a-skill" / "SKILL.md").write_text("---\nname: a-skill\ndescription: a\nallowed_agents: [o]\nimplementation_surface: prompted\n---\n")
        (root / "b-skill" / "SKILL.md").write_text("---\nname: b-skill\ndescription: b\nallowed_agents: [o]\nimplementation_surface: prompted\n---\n")
        store = SkillStore(roots=[root])
        store.scan()
        names = [r.name for r in store.skills.get("_shared", [])]
        assert names == ["a-skill", "b-skill", "c-skill"]

    def test_valid_skill_record(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        record = store.find(name="valid-skill", agent_scope="oracle")
        assert record is not None
        assert record.name == "valid-skill"
        assert record.description == "A valid test skill."
        assert record.allowed_agents == ("oracle",)
        assert record.implementation_surface == "prompted"
        assert record.first_slice is True
        assert record.success_signal == "Works correctly."
        assert "Body content." in record.body

    def test_first_slice_defaults_true(self):
        # Create a skill without first_slice key
        root = Path(__file__).with_name("fixtures")
        store = SkillStore(roots=[root])
        store.scan()
        record = store.find(name="valid-skill", agent_scope="oracle")
        assert record is not None
        assert record.first_slice is True

    def test_first_slice_explicit_false(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        record = store.find(name="non-first-slice", agent_scope="oracle")
        assert record is None  # filtered out by default first_slice_only=False
        # But if we set first_slice_only=True, it should be skipped
        store2 = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS], first_slice_only=True)
        store2.scan()
        assert store2.find(name="non-first-slice", agent_scope="oracle") is None
        assert any("non-first-slice" in str(p) for p, _ in store2.skipped)

    def test_first_slice_only_filter_reason(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS], first_slice_only=True)
        store.scan()
        skipped_paths = [p for p, _ in store.skipped]
        assert any("non-first-slice" in str(p) for p in skipped_paths)
        reasons = [r for _, r in store.skipped]
        assert any("first_slice_only filter" in r for r in reasons)

    def test_invalid_name_rejected(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        bad_name_errors = [msg for p, msg in store.errors if "bad-name" in str(p)]
        assert any("invalid name" in msg for msg in bad_name_errors)

    def test_missing_frontmatter_rejected(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        missing_fm_errors = [msg for p, msg in store.errors if "missing-frontmatter" in str(p)]
        assert any("frontmatter" in msg for msg in missing_fm_errors)

    def test_duplicate_name_rejected(self, tmp_path: Path):
        root = tmp_path / "agents" / "oracle" / "skills"
        (root / "dup" / "SKILL.md").parent.mkdir(parents=True)
        (root / "dup2" / "SKILL.md").parent.mkdir(parents=True)
        text = "---\nname: dup\ndescription: d\nallowed_agents: [oracle]\nimplementation_surface: prompted\n---\n"
        (root / "dup" / "SKILL.md").write_text(text)
        (root / "dup2" / "SKILL.md").write_text(text)
        store = SkillStore(roots=[tmp_path])
        store.scan()
        dup_errors = [msg for p, msg in store.errors if "duplicate name" in msg]
        assert len(dup_errors) == 1
        assert "dup" in dup_errors[0]

    def test_agent_star_rejected(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        star_errors = [
            msg for p, msg in store.errors
            if "agent-star-reject" in str(p)
        ]
        assert len(star_errors) == 1
        assert "agent-scoped skills must not declare allowed_agents: ['*']" in star_errors[0]

    def test_cross_cutting_star_allowed(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        record = store.find(name="shared-skill", agent_scope="_shared")
        assert record is not None
        assert record.allowed_agents == ("*",)

    def test_redacted_skill_rejected(self):
        store = SkillStore(roots=[ORACLE_SKILLS, SHARED_SKILLS])
        store.scan()
        redacted_errors = [msg for p, msg in store.errors if "redacted-skill" in str(p)]
        assert any("redacted content" in msg for msg in redacted_errors)
        # Error message must NOT echo the payload
        for msg in redacted_errors:
            assert "sk-proj" not in msg

    def test_body_size_cap(self, tmp_path: Path):
        root = tmp_path / "skills"
        (root / "huge" / "SKILL.md").parent.mkdir(parents=True)
        body = "x" * (256 * 1024 + 1)
        text = f"---\nname: huge\ndescription: d\nallowed_agents: [o]\nimplementation_surface: prompted\n---\n{body}"
        (root / "huge" / "SKILL.md").write_text(text)
        store = SkillStore(roots=[tmp_path])
        store.scan()
        size_errors = [msg for p, msg in store.errors if "huge" in str(p)]
        assert any("body exceeds 256KB" in msg for msg in size_errors)


class TestLightweightImport:
    def test_import_does_not_pull_heavy_deps(self):
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
