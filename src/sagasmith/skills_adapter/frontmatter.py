"""Hand-rolled YAML-lite frontmatter parser.

We avoid adding PyYAML for a handful of files (consistent with Plan 03-01's
hand-rolled TOML writer decision). The supported subset is narrow but
well-defined — unsupported shapes fail closed with FrontmatterError.
"""

from __future__ import annotations

import re

from sagasmith.skills_adapter.errors import FrontmatterError

SUPPORTED_SUBSET = """\
Supported SKILL.md frontmatter (YAML-lite):

- Scalar strings: `key: value` or `key: "quoted value"`
- Booleans: `key: true | True | false | False`
- Integers: `key: 42`
- Flow-style lists of strings: `key: [a, b, "c"]`

NOT supported:
- Folded blocks (`>`), literal blocks (`|`)
- Nested mappings (indented sub-keys)
- Anchors, aliases, multi-line strings
- Block-style lists (with leading `-`)

Unsupported shapes raise FrontmatterError.
"""

_DELIMITER = "---"
_KEY_VAL_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$")
_LIST_RE = re.compile(r"^\[(.*)\]$")


def _parse_value(raw: str, key: str) -> object:
    raw = raw.strip()
    if not raw:
        # Empty values are not supported in YAML-lite; they usually indicate
        # a nested map or block-style list on subsequent indented lines,
        # which will be rejected by the indentation guard in parse_frontmatter.
        raise FrontmatterError(f"{key}: unsupported YAML feature: empty value")
    # Detect unsupported features explicitly
    if raw in (">", "|") or raw.startswith(">") or raw.startswith("|"):
        raise FrontmatterError(f"{key}: unsupported YAML feature: folded/literal block")
    if raw.startswith("&") or raw.startswith("*"):
        raise FrontmatterError(f"{key}: unsupported YAML feature: anchor/alias")
    # Boolean
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    # List
    m = _LIST_RE.match(raw)
    if m:
        inner = m.group(1)
        if not inner.strip():
            return []
        tokens = [t.strip().strip('"').strip("'") for t in inner.split(",")]
        return tokens
    # Integer
    if raw.lstrip("-").isdigit():
        return int(raw)
    # String (strip surrounding quotes if present)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse a SKILL.md string into (frontmatter_dict, body_str)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != _DELIMITER:
        raise FrontmatterError("missing opening delimiter (expected '---' on first line)")
    # Find closing delimiter
    closing_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == _DELIMITER:
            closing_idx = i
            break
    if closing_idx is None:
        raise FrontmatterError("missing closing delimiter")

    fm_lines = lines[1:closing_idx]
    body = "".join(lines[closing_idx + 1 :])

    # Detect nested maps via indentation: a line with leading whitespace is rejected
    data: dict[str, object] = {}
    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t"):
            raise FrontmatterError(
                f"unsupported YAML feature: indented continuation in line {line!r}"
            )
        if stripped.startswith("- "):
            raise FrontmatterError("unsupported YAML feature: block-style list")
        m = _KEY_VAL_RE.match(stripped)
        if not m:
            raise FrontmatterError(f"unparseable line: {line!r}")
        key, raw = m.group(1), m.group(2)
        data[key] = _parse_value(raw, key)

    return data, body
