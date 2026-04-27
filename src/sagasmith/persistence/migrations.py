"""Migration runner for SQLite campaign databases."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply pending migrations and return the list of versions applied."""
    current = current_schema_version(conn)
    applied: list[int] = []
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        match = re.match(r"^(\d+)_", sql_file.name)
        if not match:
            continue
        version = int(match.group(1))
        if version > current:
            sql = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            applied.append(version)
    if applied:
        conn.commit()
    return applied


def current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if the table does not exist."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0
