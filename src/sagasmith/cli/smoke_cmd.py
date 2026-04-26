"""No-paid-call smoke command."""

from __future__ import annotations

import subprocess
import sys
from enum import StrEnum
from typing import Annotated

import typer

from sagasmith.evals.harness import run_smoke


class SmokeMode(StrEnum):
    """Supported smoke execution modes."""

    FAST = "fast"
    PYTEST = "pytest"


def smoke(
    mode: Annotated[
        SmokeMode,
        typer.Option(
            "--mode",
            case_sensitive=False,
            help="fast = in-process harness; pytest = `pytest -m smoke`.",
        ),
    ] = SmokeMode.FAST,
) -> None:
    """Run the no-paid-call smoke suite (FOUND-04)."""

    if mode == SmokeMode.FAST:
        result = run_smoke()
        typer.echo(result.format())
        if not result.ok:
            raise typer.Exit(code=1)
        return

    command = [sys.executable, "-m", "pytest", "-q", "-m", "smoke"]
    proc = subprocess.run(command, check=False)
    raise typer.Exit(code=proc.returncode)
