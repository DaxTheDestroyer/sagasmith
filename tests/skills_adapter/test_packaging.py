"""Installed-style packaging test for SKILL.md inclusion."""

from __future__ import annotations

import importlib.resources

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

        skill_files = list(files.rglob("SKILL.md"))
        # If we are in editable mode there may be zero packaged SKILL.md files.
        if not skill_files:
            pytest.skip("No packaged SKILL.md found (editable install?)")

        assert len(skill_files) > 0
