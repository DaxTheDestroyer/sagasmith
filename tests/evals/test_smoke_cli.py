"""End-to-end no-paid-call smoke CLI tests."""

import pytest
from typer.testing import CliRunner

from sagasmith.cli.main import app

pytestmark = pytest.mark.smoke


def test_smoke_fast_mode_exits_zero():
    result = CliRunner().invoke(app, ["smoke", "--mode", "fast"])
    assert result.exit_code == 0, result.stdout
    assert "checks passed" in result.stdout


def test_smoke_fast_mode_prints_every_check():
    result = CliRunner().invoke(app, ["smoke", "--mode", "fast"])
    for name in (
        "schema.round_trip.saga_state",
        "schema.validation.rejects_missing_field",
        "schema.export.full_coverage",
        "redaction.exported_schemas_clean",
        "state.compact_references",
    ):
        assert name in result.stdout, f"missing check name {name!r} in output:\n{result.stdout}"


def test_smoke_default_mode_is_fast():
    result = CliRunner().invoke(app, ["smoke"])
    assert result.exit_code == 0
    assert "checks passed" in result.stdout
