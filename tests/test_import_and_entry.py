"""Import and entry point smoke tests for the SagaSmith scaffold."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

from typer.testing import CliRunner


ROOT = Path(__file__).resolve().parents[1]
SUBPACKAGES = {
    "app",
    "cli",
    "tui",
    "graph",
    "agents",
    "services",
    "providers",
    "persistence",
    "memory",
    "schemas",
    "evals",
    "skills",
}


def project_version() -> str:
    """Return the version declared in pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    return str(pyproject["project"]["version"])


def test_package_imports() -> None:
    """The root package imports and exposes the pyproject version."""
    import sagasmith

    assert sagasmith.__version__ == project_version()


def test_cli_version_subcommand() -> None:
    """The Typer version command prints the package version."""
    import sagasmith
    from sagasmith.cli.main import app

    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert sagasmith.__version__ in result.stdout


def test_cli_help() -> None:
    """The Typer app exposes package help text."""
    from sagasmith.cli.main import app

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "sagasmith" in result.stdout.lower()


def test_subpackages_importable() -> None:
    """Every planned top-level subpackage imports cleanly."""
    for subpackage in sorted(SUBPACKAGES):
        module = importlib.import_module(f"sagasmith.{subpackage}")
        assert module is not None
