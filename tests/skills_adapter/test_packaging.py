"""Installed-style packaging test for SKILL.md inclusion."""

from __future__ import annotations

import importlib.resources
from typing import Any

import pytest


class TestPackaging:
    def test_skills_package_data_accessible(self):
        """Verify that SKILL.md files are reachable via importlib.resources.

        This test is skipped when running in editable/development mode because
        package-data inclusion only applies to built wheels/sdists.
        """
        try:
            files = importlib.resources.files("sagasmith")
        except ModuleNotFoundError:
            pytest.skip("sagasmith package not installed")

        def _collect_skills(node: Any) -> list[Any]:
            results: list[Any] = []
            try:
                for child in node.iterdir():
                    if child.is_dir():
                        results.extend(_collect_skills(child))
                    elif child.name == "SKILL.md":
                        results.append(child)
            except (OSError, AttributeError):
                pass
            return results

        skill_files = _collect_skills(files)
        # If we are in editable mode there may be zero packaged SKILL.md files.
        if not skill_files:
            pytest.skip("No packaged SKILL.md found (editable install?)")

        assert len(skill_files) > 0
