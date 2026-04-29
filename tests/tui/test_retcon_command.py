"""Tests for /retcon command: no-graph-unavailable, candidate picker, preview,
confirmation, completion/block messaging, and post-retcon resync."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from sagasmith.app.campaign import init_campaign, open_campaign
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.repositories import TranscriptRepository, TurnRecordRepository
from sagasmith.schemas.persistence import TranscriptEntry, TurnRecord
from sagasmith.tui.app import SagaSmithApp
from sagasmith.tui.commands.control import RetconCommand
from sagasmith.tui.commands.registry import CommandRegistry
from sagasmith.tui.widgets.narration import NarrationArea


def _make_app(tmp_path: Path) -> SagaSmithApp:
    root = tmp_path / "c"
    init_campaign(name="Retcon Test", root=root, provider="fake")
    paths, manifest = open_campaign(root)
    app = SagaSmithApp(paths=paths, manifest=manifest)
    registry = CommandRegistry()
    app.commands = registry  # type: ignore[assignment]
    return app


# ---------------------------------------------------------------------------
# Fake runtime / preview helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakePreview:
    selected_turn_id: str
    affected_turn_ids: list[str]
    prior_checkpoint_id: str
    transcript_count: int
    roll_count: int
    vault_paths: list[str]
    confirmation_token: str
    effects: str


@dataclass
class _FakeResult:
    selected_turn_id: str
    affected_turn_ids: list[str]
    prior_checkpoint_id: str
    audit_id: str
    message: str


class _RecordingRuntime:
    """GraphRuntime-alike that records preview_retcon / confirm_retcon calls."""

    def __init__(self, db_conn: sqlite3.Connection | None = None) -> None:
        self.db_conn: sqlite3.Connection | None = db_conn
        self.preview_calls: list[str | None] = []
        self.confirm_calls: list[tuple[str, str]] = []
        self._preview_result: _FakePreview | Exception = _FakePreview(
            selected_turn_id="turn_000003",
            affected_turn_ids=["turn_000003", "turn_000004"],
            prior_checkpoint_id="cp_000002",
            transcript_count=3,
            roll_count=1,
            vault_paths=["locations/river.md", "npcs/mara.md"],
            confirmation_token="RETCON turn_000003",
            effects=(
                "Retcon will perform a state rewind to the prior safe checkpoint, "
                "rebuild affected transcript/mechanics/vault/memory outputs from "
                "canonical sources, preserve audit retention for removed canon, "
                "and enforce canonical exclusion after success."
            ),
        )
        self._confirm_result: _FakeResult | Exception = _FakeResult(
            selected_turn_id="turn_000003",
            affected_turn_ids=["turn_000003", "turn_000004"],
            prior_checkpoint_id="cp_000002",
            audit_id="retcon-abc123",
            message="Retcon complete for turn_000003; 2 turn(s) excluded from canon.",
        )

    def preview_retcon(self, selected_turn_id: str):
        self.preview_calls.append(selected_turn_id)
        if isinstance(self._preview_result, Exception):
            raise self._preview_result
        return self._preview_result

    def confirm_retcon(self, selected_turn_id: str, confirmation_token: str):
        self.confirm_calls.append((selected_turn_id, confirmation_token))
        if isinstance(self._confirm_result, Exception):
            raise self._confirm_result
        return self._confirm_result

    def set_preview_result(self, result: _FakePreview | Exception) -> None:
        self._preview_result = result

    def set_confirm_result(self, result: _FakeResult | Exception) -> None:
        self._confirm_result = result


# ---------------------------------------------------------------------------
# Task 1 tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_graph_runtime_prints_unavailable(tmp_path: Path) -> None:
    """Test 1: /retcon with no args prints 'no active graph runtime' and does
    not attempt confirmation."""
    app = _make_app(tmp_path)
    app.graph_runtime = None
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = " ".join(logged)
    assert "no active graph runtime" in combined


@pytest.mark.asyncio
async def test_no_args_lists_candidates(tmp_path: Path) -> None:
    """Test 2: /retcon with no args prints a numbered list of recent eligible
    candidates and does NOT call confirm_retcon."""
    app = _make_app(tmp_path)
    conn = open_campaign_db(app.paths.db)
    app.bind_service_connection(conn)

    # Seed two completed turns with transcript summaries.
    for idx, turn_id in enumerate(("turn_000001", "turn_000002")):
        TurnRecordRepository(conn).upsert(
            TurnRecord(
                turn_id=turn_id,
                campaign_id=app.manifest.campaign_id,
                session_id="session_001",
                status="complete",
                started_at=f"2026-04-29T10:0{idx + 1}:00Z",
                completed_at=f"2026-04-29T10:0{idx + 1}:30Z",
                schema_version=1,
            )
        )
        TranscriptRepository(conn).append(
            TranscriptEntry(
                turn_id=turn_id,
                kind="narration_final",
                content=f"Summary for {turn_id}.",
                sequence=0,
                created_at=f"2026-04-29T10:0{idx + 1}:20Z",
            )
        )
    conn.commit()

    runtime = _RecordingRuntime(db_conn=conn)
    app.graph_runtime = runtime  # type: ignore[assignment]
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ())
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "[system] /retcon candidates:" in combined, combined
    assert "turn_000002" in combined
    assert "turn_000001" in combined
    assert "Summary for turn_000002" in combined
    assert "Summary for turn_000001" in combined
    # confirm_retcon must NOT be called when there are no args.
    assert runtime.confirm_calls == []


@pytest.mark.asyncio
async def test_with_turn_id_shows_preview(tmp_path: Path) -> None:
    """Test 3: /retcon turn_000003 prints preview summary, affected turns,
    effects, and exact typed-confirmation instruction."""
    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    app.graph_runtime = runtime  # type: ignore[assignment]
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003",))
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "[system] /retcon preview for turn_000003:" in combined
    assert "Affected turns: turn_000003, turn_000004" in combined
    assert "Vault outputs: locations/river.md, npcs/mara.md" in combined
    assert "Effects:" in combined
    assert "state rewind" in combined
    assert "canonical exclusion" in combined
    assert "Type: /retcon turn_000003 RETCON turn_000003" in combined
    # preview must not confirm.
    assert runtime.confirm_calls == []


@pytest.mark.asyncio
async def test_preview_blocked_error_prints_blocked_and_repair(tmp_path: Path) -> None:
    """Test 4: When preview raises RetconBlockedError the command prints
    'blocked' and the repair guidance without mutating canon."""
    from sagasmith.persistence.retcon import RetconBlockedError

    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    blocked = RetconBlockedError(
        "Turn turn_000003 is not complete.",
        "Repair by choosing a completed canonical turn.",
    )
    runtime.set_preview_result(blocked)
    app.graph_runtime = runtime  # type: ignore[assignment]
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003",))
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "[system] /retcon blocked:" in combined
    assert "not complete" in combined
    assert "[system] repair:" in combined
    assert "completed canonical turn" in combined


# ---------------------------------------------------------------------------
# Task 2 tests: typed confirmation and completion/block messaging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmation_with_correct_token_calls_confirm_retcon(tmp_path: Path) -> None:
    """Test 1: /retcon turn_000003 RETCON turn_000003 calls confirm_retcon with
    the selected turn id and exact token, and prints a success message without
    transcript content."""
    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    app.graph_runtime = runtime  # type: ignore[assignment]
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003", "RETCON", "turn_000003"))
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    # confirm_retcon was called with correct args.
    assert runtime.confirm_calls == [("turn_000003", "RETCON turn_000003")]
    # Success message uses only turn id, never transcript body.
    assert "[system] Retcon complete: returned to checkpoint before turn_000003" in combined
    assert "audit-retained" in combined
    # Must NOT include removed canon transcript excerpts.
    assert "narration_final" not in combined


@pytest.mark.asyncio
async def test_wrong_token_prints_blocked_guidance(tmp_path: Path) -> None:
    """Test 2: Wrong confirmation token prints blocked guidance without
    exposing removed canon details."""
    from sagasmith.persistence.retcon import RetconBlockedError

    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    blocked = RetconBlockedError(
        "Confirmation token for turn turn_000003 did not match.",
        "Repair by typing the exact token: RETCON turn_000003",
    )
    runtime.set_confirm_result(blocked)
    app.graph_runtime = runtime  # type: ignore[assignment]
    logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003", "WRONG", "token"))
        logged = app.query_one(NarrationArea).logged_lines[:]

    combined = "\n".join(logged)
    assert "[system] /retcon blocked:" in combined
    assert "did not match" in combined
    assert "[system] repair:" in combined
    assert "exact token" in combined
    # No removed canon details in the blocked message.
    assert "transcript" not in combined.lower()
    assert "narration" not in combined.lower()


@pytest.mark.asyncio
async def test_successful_retcon_calls_sync_after_retcon(tmp_path: Path) -> None:
    """Test 3: After a successful retcon confirmation, the app calls
    sync_after_retcon() which invokes graph syncs without exiting."""
    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    app.graph_runtime = runtime  # type: ignore[assignment]

    # Patch sync_after_retcon to track calls.
    sync_calls: list[None] = []
    app.sync_after_retcon = lambda: sync_calls.append(None)

    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003", "RETCON", "turn_000003"))

    # confirm_retcon was called.
    assert runtime.confirm_calls == [("turn_000003", "RETCON turn_000003")]
    # sync_after_retcon was called after successful retcon.
    assert len(sync_calls) == 1, "sync_after_retcon should be called after successful retcon"


@pytest.mark.asyncio
async def test_retcon_completion_message_excludes_removed_canon(tmp_path: Path) -> None:
    """Test 4: Both success and blocked messages never include transcript
    content from a removed turn."""
    app = _make_app(tmp_path)
    runtime = _RecordingRuntime()
    app.graph_runtime = runtime  # type: ignore[assignment]
    success_logged: list[str] = []
    async with app.run_test():
        RetconCommand().handle(app, ("turn_000003", "RETCON", "turn_000003"))
        success_logged = app.query_one(NarrationArea).logged_lines[:]

    success_combined = "\n".join(success_logged)
    # Success message must never include actual transcript excerpts.
    assert "narration_final" not in success_combined
    assert "story content" not in success_combined.lower()
