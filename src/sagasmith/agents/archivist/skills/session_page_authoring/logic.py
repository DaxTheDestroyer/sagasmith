"""Author Obsidian-compatible end-of-session vault pages."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime

from sagasmith.persistence.turn_history import (
    CanonicalTurnHistory,
    SessionRollRow,
    SessionTranscriptRow,
)
from sagasmith.vault import VaultPage
from sagasmith.vault.page import SessionFrontmatter

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def draft_session_page(
    session_number: int,
    campaign_id: str,
    history: CanonicalTurnHistory,
    *,
    date_in_game: str = "unknown",
    date_real: str | None = None,
) -> VaultPage:
    """Draft ``sessions/session_NNN.md`` from canonical completed turn records.
    date_real defaults to today if not provided (runtime Adapter controls it for determinism)."""

    session_id = f"session_{session_number:03d}"
    source = history.session_page_source(campaign_id, session_id)
    transcript_rows = list(source.transcript_rows)
    roll_rows = list(source.roll_rows)
    linked_ids = _linked_ids(row.content for row in transcript_rows)

    real_date = date_real if date_real is not None else datetime.now(UTC).date().isoformat()
    frontmatter = SessionFrontmatter(
        id=session_id,
        type="session",
        name=f"Session {session_number}",
        aliases=[f"Session {session_number}"],
        visibility="player_known",
        first_encountered=session_id,
        number=session_number,
        date_real=real_date,
        date_in_game=date_in_game,
        location_start=_first_with_prefix(linked_ids, "loc_"),
        location_end=_last_with_prefix(linked_ids, "loc_"),
        npcs_encountered=sorted({value for value in linked_ids if value.startswith("npc_")}),
        quests_opened=sorted({value for value in linked_ids if value.startswith("quest_")}),
        quests_closed=[],
        callbacks_seeded=sorted({value for value in linked_ids if value.startswith("cb_")}),
        callbacks_paid_off=[],
    )
    return VaultPage(frontmatter, _build_body(transcript_rows=transcript_rows, roll_rows=roll_rows))


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
    transcript_rows: list[SessionTranscriptRow],
    roll_rows: list[SessionRollRow],
) -> str:
    narration = [row.content for row in transcript_rows if row.kind == "narration_final"]
    beats = [
        row.content.removeprefix("Beat:").strip()
        for row in transcript_rows
        if row.kind == "scene_brief"
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
        for row in roll_rows:
            mod_text = f"+{row.modifier}" if row.modifier >= 0 else str(row.modifier)
            dc_text = str(row.dc) if row.dc is not None else "—"
            lines.append(
                f"| {row.roll_id} | {row.die} | {row.natural} | {mod_text} | {row.total} | {dc_text} |"
            )
    else:
        lines.append("| — | — | — | — | — | — |")
    return "\n".join(lines)
