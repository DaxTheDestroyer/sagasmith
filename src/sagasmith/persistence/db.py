"""SQLite campaign database connection wrapper."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def campaign_db(path: Path) -> Generator[sqlite3.Connection]:
    """Open a campaign SQLite DB with proper settings and close on exit."""
    conn = open_campaign_db(path)
    try:
        yield conn
    finally:
        conn.close()


def open_campaign_db(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a campaign SQLite DB connection with WAL and foreign keys enabled."""
    uri = f"file:{path}?mode=ro" if read_only else f"file:{path}"
    conn = sqlite3.connect(
        uri,
        uri=True,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if the table does not exist."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0
