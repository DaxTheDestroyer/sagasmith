"""
Enforce the dev-harness / SagaSmith runtime boundary.

The rule (AGENTS.md §Hard Context Separation): SagaSmith runtime code must
not reference coding-harness artifacts.  Any Python file under src/sagasmith/
or tests/ that contains a forbidden token is a violation.

Forbidden tokens are paths and filenames that belong exclusively to the
coding harness (Claude Code, Kilo, GSD, mattpocock skills).  They must
never appear as string literals or import targets in runtime or test code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Literal string fragments that must not appear inside src/sagasmith/ or tests/
FORBIDDEN_TOKENS: list[str] = [
    ".kilo/",
    ".kilo\\",
    ".kilocode/",
    ".kilocode\\",
    ".agents/",
    ".agents\\",
    ".planning/",
    ".planning\\",
    "AGENTS.md",
    "CONTEXT.md",
    "CONTEXT-MAP.md",
    "kilo.json",
    "skills-lock.json",
]

# Top-level module name prefixes that must not appear in import statements
# inside src/sagasmith/
FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "kilo",
    "kilocode",
    "claude_code",
)


_THIS_FILE = Path(__file__).resolve()


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.resolve() != _THIS_FILE)


def _check_tokens(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [tok for tok in FORBIDDEN_TOKENS if tok in text]


def _check_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0].startswith(FORBIDDEN_IMPORT_PREFIXES):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0].startswith(FORBIDDEN_IMPORT_PREFIXES):
                bad.append(module)
    return bad


def _collect_violations() -> list[tuple[Path, str, str]]:
    """Return list of (file, kind, detail) for every violation."""
    violations: list[tuple[Path, str, str]] = []
    for directory in [
        REPO_ROOT / "src" / "sagasmith",
        REPO_ROOT / "tests",
    ]:
        for py_file in _py_files(directory):
            for tok in _check_tokens(py_file):
                violations.append((py_file, "forbidden token", repr(tok)))
            if directory == REPO_ROOT / "src" / "sagasmith":
                for imp in _check_imports(py_file):
                    violations.append((py_file, "forbidden import", imp))
    return violations


_VIOLATIONS = _collect_violations()


@pytest.mark.parametrize(
    "file,kind,detail",
    _VIOLATIONS,
    ids=[f"{v[0].relative_to(REPO_ROOT)}::{v[2]}" for v in _VIOLATIONS]
    if _VIOLATIONS
    else ["no-violations"],
)
def test_no_harness_references(file: Path, kind: str, detail: str) -> None:
    """Each entry here is a violation — this test should always pass (empty list)."""
    rel = file.relative_to(REPO_ROOT)
    raise AssertionError(
        f"Harness boundary violation in {rel}\n"
        f"  {kind}: {detail}\n"
        f"  SagaSmith runtime code must not reference dev-harness artifacts.\n"
        f"  See AGENTS.md §Hard Context Separation and LAYOUT.md for the rule."
    )


def test_violation_list_is_empty() -> None:
    """Fast-fail if any violations were collected."""
    assert _VIOLATIONS == [], (
        f"{len(_VIOLATIONS)} harness boundary violation(s) found:\n"
        + "\n".join(f"  {v[0].relative_to(REPO_ROOT)}: {v[1]} {v[2]}" for v in _VIOLATIONS)
    )
