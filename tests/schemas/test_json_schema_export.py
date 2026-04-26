"""Tests for JSON Schema export and schema CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sagasmith.cli.main import app
from sagasmith.schemas.export import export_all_schemas

EXPECTED_SCHEMA_NAMES = {
    "SagaState",
    "PlayerProfile",
    "ContentPolicy",
    "HouseRules",
    "SessionState",
    "SceneBrief",
    "MemoryPacket",
    "CharacterSheet",
    "CombatState",
    "CheckProposal",
    "CheckResult",
    "RollResult",
    "StateDelta",
    "CanonConflict",
    "SafetyEvent",
    "CostState",
}


def schema_name(path: Path) -> str:
    return path.name.removesuffix(".schema.json")


def test_exported_schema_set_matches_contract(tmp_path: Path) -> None:
    paths = export_all_schemas(tmp_path)

    assert paths == sorted(paths)
    assert {schema_name(path) for path in paths} == EXPECTED_SCHEMA_NAMES


def test_every_exported_schema_is_valid_json(tmp_path: Path) -> None:
    for path in export_all_schemas(tmp_path):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "$defs" in data or "properties" in data


def test_exported_schema_files_have_deterministic_content(tmp_path: Path) -> None:
    first = export_all_schemas(tmp_path / "first")
    second = export_all_schemas(tmp_path / "second")

    first_by_name = {path.name: path.read_bytes() for path in first}
    second_by_name = {path.name: path.read_bytes() for path in second}
    assert first_by_name == second_by_name


def test_cli_schema_export_writes_files(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["schema", "export", "--out", str(tmp_path)])

    assert result.exit_code == 0, result.output
    schema_path = tmp_path / "SagaState.schema.json"
    assert schema_path.exists()
    assert json.loads(schema_path.read_text(encoding="utf-8"))


def test_cli_schema_export_defaults_to_schemas_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["schema", "export"])

    assert result.exit_code == 0, result.output
    schema_path = tmp_path / "schemas" / "SagaState.schema.json"
    assert schema_path.exists()
    assert json.loads(schema_path.read_text(encoding="utf-8"))
