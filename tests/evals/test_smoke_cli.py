"""End-to-end no-paid-call smoke CLI tests."""

import subprocess

import pytest
from typer.testing import CliRunner

from sagasmith.cli.main import app
from sagasmith.cli.smoke_cmd import SmokeMode

pytestmark = pytest.mark.smoke


def test_smoke_fast_mode_exits_zero():
    result = CliRunner().invoke(app, ["smoke", "--mode", "fast"])
    assert result.exit_code == 0, result.stdout
    assert "checks passed" in result.stdout
    assert "13/13" in result.stdout


def test_smoke_fast_mode_prints_every_check():
    result = CliRunner().invoke(app, ["smoke", "--mode", "fast"])
    for name in (
        "schema.round_trip.saga_state",
        "schema.validation.rejects_missing_field",
        "schema.export.full_coverage",
        "redaction.exported_schemas_clean",
        "state.compact_references",
        "schema.hp_invariant.rejects_over_max",
        "redaction.openai_project_key.labeled",
        "provider.fake.round_trip",
        "cost.warning.fires_once_per_threshold",
        "cost.hard_stop.before_call",
        "persistence.turn_close.transaction_ordering",
        "cli.init.creates_storage",
        "rules_first_vertical_slice",
    ):
        assert name in result.stdout, f"missing check name {name!r} in output:\n{result.stdout}"


def test_smoke_default_mode_is_fast():
    result = CliRunner().invoke(app, ["smoke"])
    assert result.exit_code == 0
    assert "checks passed" in result.stdout


def test_smoke_mode_includes_mvp() -> None:
    assert SmokeMode.MVP == "mvp"


def test_smoke_mvp_mode_exits_zero_from_local_entrypoint() -> None:
    proc = subprocess.run(
        ["uv", "run", "sagasmith", "smoke", "--mode", "mvp"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK  mvp.init" in proc.stdout
    assert "OK  mvp.resume" in proc.stdout
    assert "mvp.resume" in proc.stdout
