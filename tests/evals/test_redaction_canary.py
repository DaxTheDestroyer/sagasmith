"""Redaction canary smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.evals.redaction import DEFAULT_SECRET_PATTERNS, RedactionCanary
from sagasmith.schemas.export import export_all_schemas

pytestmark = pytest.mark.smoke


EXPECTED_LABELS = {
    "openrouter_key",
    "openai_key",
    "anthropic_key",
    "bearer_header",
    "aws_access_key",
    "high_entropy_hex",
}


def test_canary_detects_fixture_secrets(redaction_sample_text):
    labels = {hit.label for hit in RedactionCanary().scan(redaction_sample_text)}
    assert len(labels) >= 4
    assert {"openrouter_key", "bearer_header", "aws_access_key", "high_entropy_hex"} <= labels


def test_canary_accepts_safe_text():
    text = "The player opened the tavern door. Roll Perception DC 15."
    assert RedactionCanary().scan(text) == []


def test_exported_schemas_have_no_secret_shaped_strings(tmp_path: Path):
    paths = export_all_schemas(tmp_path)
    blob = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert RedactionCanary().scan(blob) == []


def test_default_pattern_labels_exact():
    assert {label for label, _ in DEFAULT_SECRET_PATTERNS} == EXPECTED_LABELS
