"""Author Obsidian-compatible end-of-session vault pages."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sagasmith.persistence.turn_history import CanonicalTurnHistory
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import SessionFrontmatter

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def author_session(
    session_number: int,
    campaign_id: str,
    db_conn: sqlite3.Connection,
    vault_service: VaultService,
    *,
    history: CanonicalTurnHistory | None = None,
    date_in_game: str = "unknown",
) -> str:
    """Create or refresh ``sessions/session_NNN.md`` from completed turn records."""

    session_id = f"session_{session_number:03d}"
    _history = history if history is not None else CanonicalTurnHistory(db_conn)
    turns = _history.session_turn_ids(campaign_id, session_id)
    transcript_rows = _transcript_rows(db_conn, turns)
    roll_rows = _roll_rows(db_conn, turns)
    linked_ids = _linked_ids(row[2] for row in transcript_rows)

    frontmatter = SessionFrontmatter(
        id=session_id,
        type="session",
        name=f"Session {session_number}",
        aliases=[f"Session {session_number}"],
        visibility="player_known",
        first_encountered=session_id,
        number=session_number,
        date_real=datetime.now(UTC).date().isoformat(),
        date_in_game=date_in_game,
        location_start=_first_with_prefix(linked_ids, "loc_"),
        location_end=_last_with_prefix(linked_ids, "loc_"),
        npcs_encountered=sorted({value for value in linked_ids if value.startswith("npc_")}),
        quests_opened=sorted({value for value in linked_ids if value.startswith("quest_")}),
        quests_closed=[],
        callbacks_seeded=sorted({value for value in linked_ids if value.startswith("cb_")}),
        callbacks_paid_off=[],
    )
    page = VaultPage(frontmatter, _build_body(transcript_rows=transcript_rows, roll_rows=roll_rows))
    relative_path = Path("sessions") / f"{session_id}.md"
    vault_service.write_page(page, relative_path)
    return relative_path.as_posix()


def _transcript_rows(
    conn: sqlite3.Connection, turn_ids: list[str]
) -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for turn_id in turn_ids:
        rows.extend(
            (str(row[0]), str(row[1]), str(row[2]), int(row[3]))
            for row in conn.execute(
                """
                SELECT turn_id, kind, content, sequence
                  FROM transcript_entries
                 WHERE turn_id = ?
                 ORDER BY sequence
                """,
                (turn_id,),
            ).fetchall()
        )
    return rows


def _roll_rows(
    conn: sqlite3.Connection, turn_ids: list[str]
) -> list[tuple[str, str, int, int, int, int]]:
    rows: list[tuple[str, str, int, int, int, int]] = []
    for turn_id in turn_ids:
        rows.extend(
            (str(row[0]), str(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]))
            for row in conn.execute(
                """
                SELECT roll_id, die, natural, modifier, total, dc
                  FROM roll_logs
                 WHERE turn_id = ?
                 ORDER BY timestamp, roll_id
                """,
                (turn_id,),
            ).fetchall()
        )
    return rows


def _linked_ids(contents: Iterable[str]) -> list[str]:
    ids: list[str] = []
    for content in contents:
        for match in _WIKILINK_RE.finditer(content):
            ids.append(match.group(1))
    return ids


def _first_with_prefix(values: list[str], prefix: str) -> str | None:
    return next((value for value in values if value.startswith(prefix)), None)


def _last_with_prefix(values: list[str], prefix: str) -> str | None:
    matches = [value for value in values if value.startswith(prefix)]
    return matches[-1] if matches else None


def _build_body(
    *,
    transcript_rows: list[tuple[str, str, str, int]],
    roll_rows: list[tuple[str, str, int, int, int, int]],
) -> str:
    narration = [
        content
        for _turn_id, kind, content, _sequence in transcript_rows
        if kind == "narration_final"
    ]
    beats = [
        content.removeprefix("Beat:").strip()
        for _turn_id, kind, content, _sequence in transcript_rows
        if kind == "scene_brief"
    ]
    lines = [
        "## Summary",
        "",
        *(narration or ["No completed narration was recorded."]),
        "",
        "## Beats",
        "",
    ]
    lines.extend(
        f"{index}. {beat}" for index, beat in enumerate(beats or ["No beats recorded."], start=1)
    )
    lines.extend(
        [
            "",
            "## Rolls",
            "",
            "| Roll | Die | Natural | Mod | Total | DC |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    if roll_rows:
        for roll_id, die, natural, modifier, total, dc in roll_rows:
            mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
            lines.append(f"| {roll_id} | {die} | {natural} | {mod_text} | {total} | {dc} |")
    else:
        lines.append("| — | — | — | — | — | — |")
    return "\n".join(lines)
