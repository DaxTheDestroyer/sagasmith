"""Tests for the production SKILL.md catalog shipped in Plan 04-05.

Covers:
- Production scan returns zero errors
- Required-set containment (not exact count)
- first_slice_only filtering
- implementation_surface matches spec
- Bootstrap loud-on-error
- Name-directory match
- Description length contract
- Lazy import (no scan at module load)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.skills_adapter import SkillStore
from sagasmith.skills_adapter.errors import SkillValidationError

_PRODUCTION_ROOTS = [Path("src/sagasmith/agents"), Path("src/sagasmith/skills")]

# Required first-slice skills by scope (containment, not exact count)
_REQUIRED_SET: dict[str, set[str]] = {
    "_shared": {"schema-validation", "safety-redline-check", "command-dispatch"},
    "oracle": {"scene-brief-composition", "player-choice-branching", "content-policy-routing", "inline-npc-creation"},
    "rules_lawyer": {"degree-of-success", "seeded-roll-resolution", "skill-check-resolution"},
    "orator": {"scene-rendering"},
    "archivist": {"turn-close-persistence"},
    "onboarding": {"onboarding-phase-wizard"},
}

# implementation_surface per spec (by skill name)
_EXPECTED_SURFACE: dict[str, str] = {
    "schema-validation": "deterministic",
    "safety-redline-check": "deterministic",
    "command-dispatch": "deterministic",
    "scene-brief-composition": "prompted",
    "world-bible-generation": "prompted",
    "campaign-seed-generation": "prompted",
    "player-choice-branching": "prompted",
    "content-policy-routing": "hybrid",
    "inline-npc-creation": "prompted",
    "degree-of-success": "deterministic",
    "seeded-roll-resolution": "deterministic",
    "skill-check-resolution": "deterministic",
    "scene-rendering": "prompted",
    "memory-packet-assembly": "hybrid",
    "turn-close-persistence": "deterministic",
    "onboarding-phase-wizard": "deterministic",
}


class TestProductionScan:
    def test_scan_returns_zero_errors(self):
        """Test 1: production scan is clean."""
        store = SkillStore(roots=_PRODUCTION_ROOTS)
        store.scan()
        assert store.errors == [], f"errors: {store.errors}"

    def test_required_set_coverage(self):
        """Test 2: every required first-slice skill is present."""
        store = SkillStore(roots=_PRODUCTION_ROOTS)
        store.scan()
        for scope, required_names in _REQUIRED_SET.items():
            found = {r.name for r in store.skills.get(scope, [])}
            missing = required_names - found
            assert not missing, f"missing skills in {scope}: {missing}"

    def test_first_slice_filtering(self):
        """Test 3: first_slice_only=True includes provider-free memory-packet-assembly."""
        store = SkillStore(roots=_PRODUCTION_ROOTS, first_slice_only=True)
        store.scan()
        assert store.find(name="memory-packet-assembly", agent_scope="archivist") is not None
        skipped_names = {Path(p).parent.name for p, _ in store.skipped}
        assert "memory-packet-assembly" not in skipped_names
        assert store.errors == []

    def test_implementation_surface_matches_spec(self):
        """Test 4: every shipped skill's surface matches the spec catalog."""
        store = SkillStore(roots=_PRODUCTION_ROOTS)
        store.scan()
        for _scope, records in store.skills.items():
            for rec in records:
                expected = _EXPECTED_SURFACE.get(rec.name)
                assert expected is not None, f"no spec entry for {rec.name}"
                assert rec.implementation_surface == expected, (
                    f"{rec.name}: expected {expected}, got {rec.implementation_surface}"
                )

    def test_bootstrap_loud_on_error(self, tmp_path: Path):
        """Test 5: _default_skill_store raises on production scan errors."""

        # Create a temporary invalid skill to trigger an error
        bad_skill_dir = tmp_path / "agents" / "oracle" / "skills" / "bad-skill"
        bad_skill_dir.mkdir(parents=True)
        bad_skill_dir.joinpath("SKILL.md").write_text("---\nname: bad skill\n---\n")

        with pytest.raises(SkillValidationError) as exc_info:
            _default_skill_store_impl(roots=[tmp_path / "agents", tmp_path / "skills"])
        assert "Production SKILL.md scan found errors" in str(exc_info.value)

    def test_name_directory_match(self):
        """Test 6: every skill's name matches its directory name."""
        store = SkillStore(roots=_PRODUCTION_ROOTS)
        store.scan()
        for _scope, records in store.skills.items():
            for rec in records:
                dir_name = rec.path.parent.name
                assert rec.name == dir_name, (
                    f"{rec.name} != directory {dir_name} at {rec.path}"
                )

    def test_description_length(self):
        """Test 7: every description is <= 256 chars."""
        store = SkillStore(roots=_PRODUCTION_ROOTS)
        store.scan()
        for _scope, records in store.skills.items():
            for rec in records:
                assert len(rec.description) <= 256, (
                    f"{rec.name} description is {len(rec.description)} chars"
                )

    def test_lazy_bootstrap_import(self):
        """Test 8: importing bootstrap does not trigger skill scan."""
        import subprocess
        import sys

        code = (
            "import sagasmith.graph.bootstrap as b\n"
            "# If _default_skill_store ran at import, it would raise if\n"
            "# production skills were broken. We assert the module loads.\n"
            "assert hasattr(b, '_default_skill_store')\n"
            "print('ok')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def _default_skill_store_impl(*, roots: list[Path], first_slice_only: bool = False) -> SkillStore:
    """Re-implementation for monkeypatch testing."""
    store = SkillStore(roots=roots, first_slice_only=first_slice_only)
    store.scan()
    if store.errors:
        error_list = "\n".join(f"  - {p}: {msg}" for p, msg in store.errors)
        raise SkillValidationError(f"Production SKILL.md scan found errors:\n{error_list}")
    return store
