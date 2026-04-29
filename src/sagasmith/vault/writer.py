"""Atomic file writer with post-write YAML validation."""

from __future__ import annotations

import os
from pathlib import Path

from .page import BaseVaultFrontmatter, VaultPage


def atomic_write(page: VaultPage, target: Path) -> None:
    """Write a vault page using atomic file replacement.

    Steps:
    1. Serialize page to markdown.
    2. Write to a temporary file in the same directory (open in binary write mode).
    3. Flush and fsync the file descriptor.
    4. Close temp file.
    5. Atomically replace the target via os.replace().
    6. Re-read the target, parse frontmatter, validate with page.frontmatter class.
    7. On any error: raise ValueError, clean up temp file.

    Args:
        page: The VaultPage to persist.
        target: Final canonical path for the vault page.

    Raises:
        ValueError: If post-write validation fails or any I/O error occurs.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    content = page.as_markdown()
    tmp_path = target.with_suffix(".tmp")
    try:
        # Write temp file with explicit binary write and fsync
        with open(tmp_path, "wb") as f:
            f.write(content.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        # Atomic replace
        os.replace(tmp_path, target)
        # Post-write validation: re-read and parse frontmatter
        _validate_written_file(target, page.frontmatter.__class__)
    except Exception as exc:
        # Clean up temp file if present
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise ValueError(f"Atomic write failed for {target}: {exc}") from exc


def _validate_written_file(path: Path, expected_type: type[BaseVaultFrontmatter]) -> None:
    """Read file, parse YAML frontmatter, and validate against expected model."""
    import yaml

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing frontmatter delimiter in {path}")
    _, front_yaml, _ = text.split("---\n", 2)
    try:
        front_dict = yaml.safe_load(front_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    # Validate against the expected frontmatter class
    try:
        expected_type.model_validate(front_dict)
    except Exception as exc:
        raise ValueError(f"Frontmatter validation failed for {path}: {exc}") from exc
