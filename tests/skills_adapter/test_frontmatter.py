"""Tests for skills_adapter.frontmatter, errors, and packaging config."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


class TestParseFrontmatter:
    def test_valid_skill_md(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = "---\nkey: value\n---\n# Body\n"
        fm, body = parse_frontmatter(text)
        assert fm == {"key": "value"}
        assert body == "# Body\n"

    def test_boolean_parsing(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        for raw, expected in [
            ("first_slice: true", True),
            ("first_slice: True", True),
            ("first_slice: false", False),
            ("first_slice: False", False),
        ]:
            text = f"---\n{raw}\n---\n"
            fm, _body = parse_frontmatter(text)
            assert fm["first_slice"] is expected, f"failed for {raw}"

    def test_integer_parsing(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = "---\ntimeout: 42\n---\n"
        fm, _body = parse_frontmatter(text)
        assert fm["timeout"] == 42
        assert isinstance(fm["timeout"], int)

    def test_quoted_string_stays_string(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = '---\ntimeout: "42"\n---\n'
        fm, _body = parse_frontmatter(text)
        assert fm["timeout"] == "42"
        assert isinstance(fm["timeout"], str)

    def test_flow_style_list(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = "---\nallowed_agents: [oracle, rules_lawyer]\n---\n"
        fm, _body = parse_frontmatter(text)
        assert fm["allowed_agents"] == ["oracle", "rules_lawyer"]

    def test_quoted_tokens_in_list(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = '---\nallowed_agents: ["*"]\n---\n'
        fm, _body = parse_frontmatter(text)
        assert fm["allowed_agents"] == ["*"]

    def test_whitespace_trimmed_in_list(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = "---\nallowed_agents: [ a , b ]\n---\n"
        fm, _body = parse_frontmatter(text)
        assert fm["allowed_agents"] == ["a", "b"]

    def test_empty_list(self):
        from sagasmith.skills_adapter.frontmatter import parse_frontmatter

        text = "---\nallowed_agents: []\n---\n"
        fm, _body = parse_frontmatter(text)
        assert fm["allowed_agents"] == []

    def test_missing_opening_delimiter(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        with pytest.raises(FrontmatterError, match="missing opening"):
            parse_frontmatter("# just body\n")

    def test_missing_closing_delimiter(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        with pytest.raises(FrontmatterError, match="missing closing"):
            parse_frontmatter("---\nkey: value\n# body\n")

    def test_folded_block_rejected(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        text = "---\ndesc: >\n  long text\n---\n"
        with pytest.raises(FrontmatterError, match="unsupported YAML feature"):
            parse_frontmatter(text)

    def test_literal_block_rejected(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        text = "---\ndesc: |\n  long\n---\n"
        with pytest.raises(FrontmatterError, match="unsupported YAML feature"):
            parse_frontmatter(text)

    def test_nested_map_rejected(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        text = "---\nopts:\n  a: 1\n---\n"
        with pytest.raises(FrontmatterError, match="unsupported YAML feature"):
            parse_frontmatter(text)

    def test_block_style_list_rejected(self):
        from sagasmith.skills_adapter.frontmatter import FrontmatterError, parse_frontmatter

        text = "---\nitems:\n  - a\n  - b\n---\n"
        with pytest.raises(FrontmatterError, match="unsupported YAML feature"):
            parse_frontmatter(text)


class TestSupportedSubset:
    def test_constant_exists_and_is_string(self):
        from sagasmith.skills_adapter.frontmatter import SUPPORTED_SUBSET

        assert isinstance(SUPPORTED_SUBSET, str)
        assert "YAML-lite" in SUPPORTED_SUBSET
        assert "Scalar strings" in SUPPORTED_SUBSET
        assert "NOT supported" in SUPPORTED_SUBSET


class TestErrorHierarchy:
    def test_all_importable(self):
        from sagasmith.skills_adapter.errors import (
            SkillAdapterError,
            SkillNotFoundError,
            SkillValidationError,
            UnauthorizedSkillError,
        )
        from sagasmith.skills_adapter.frontmatter import FrontmatterError

        assert issubclass(SkillValidationError, SkillAdapterError)
        assert issubclass(SkillNotFoundError, SkillAdapterError)
        assert issubclass(UnauthorizedSkillError, SkillAdapterError)
        assert issubclass(FrontmatterError, SkillValidationError)


class TestPyprojectPackaging:
    def test_pyproject_skill_packaging(self):
        cfg = tomllib.loads(Path("pyproject.toml").read_text())
        wheel = (
            cfg.get("tool", {})
            .get("hatch", {})
            .get("build", {})
            .get("targets", {})
            .get("wheel", {})
        )

        includes = wheel.get("include", [])
        has_include = any("SKILL.md" in str(v) for v in includes)

        force_includes = wheel.get("force-include", {})
        has_force = any("SKILL.md" in str(v) for v in force_includes.values())

        setuptools_data = cfg.get("tool", {}).get("setuptools", {}).get("package-data", {})
        has_setuptools = any(
            "SKILL.md" in str(v)
            for row in setuptools_data.values()
            for v in (row if isinstance(row, list) else [row])
        )

        assert (
            has_include or has_force or has_setuptools
        ), f"pyproject.toml must declare SKILL.md inclusion in build config; found wheel={wheel}"


class TestLightweightImport:
    def test_import_does_not_pull_heavy_deps(self):
        code = (
            "import sys\n"
            "from sagasmith.skills_adapter import parse_frontmatter, FrontmatterError, SUPPORTED_SUBSET\n"
            "from sagasmith.skills_adapter.errors import SkillAdapterError\n"
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
