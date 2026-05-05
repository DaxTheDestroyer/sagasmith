"""Architecture guard for the Agent Skills Execution Seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "sagasmith"


def _read(path: str) -> str:
    return (SRC / path).read_text(encoding="utf-8")


def test_agent_nodes_do_not_touch_activation_context_directly() -> None:
    node_files = sorted((SRC / "agents").glob("*/node.py"))

    offenders = [
        path.relative_to(REPO_ROOT)
        for path in node_files
        if "get_current_activation" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_agent_nodes_do_not_authorize_skills_via_store_find() -> None:
    node_files = sorted((SRC / "agents").glob("*/node.py"))

    offenders = [
        path.relative_to(REPO_ROOT)
        for path in node_files
        if "skill_store" in path.read_text(encoding="utf-8")
        or ".find(name=" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_load_skill_runtime_use_is_centralized() -> None:
    offenders: list[Path] = []
    allowed = {
        SRC / "skills_adapter" / "loader.py",
        SRC / "skills_adapter" / "execution.py",
    }
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "load_skill(" in text and path not in allowed:
            offenders.append(path.relative_to(REPO_ROOT))

    assert offenders == []


def test_deepened_modules_receive_skill_execution() -> None:
    assert "skill_execution" in _read("scene_planning/builder.py")
    assert "skill_store" not in _read("scene_planning/builder.py")
    assert "skill_execution" in _read("rules_turn_resolution/builder.py")
    assert "skill_store" not in _read("rules_turn_resolution/builder.py")
    assert "skill_execution" in _read("turn_plan/builder.py")
