"""Tests for turn_close extended with vault writes and sync warning handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from sagasmith.persistence.db import campaign_db
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import TurnRecordRepository
from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.errors import TrustServiceError
from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import LoreFrontmatter


def _db(tmp_path: Path) -> Path:
    return tmp_path / "turn_test.db"


def test_close_turn_with_vault_writes_success(
    tmp_path: Path,
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        # Set up a VaultService with temp player vault
        vault_service = VaultService(
            campaign_id="c1",
            player_vault_root=tmp_path / "player_vault",
        )
        vault_service.ensure_master_path()
        vault_service.ensure_player_vault()

        # Create a vault page to write
        frontmatter = LoreFrontmatter(
            id="test_lore",
            type="lore",
            name="Test Lore",
            aliases=[],
            visibility="gm_only",
            first_encountered="1",
            category="test",
        )
        page = VaultPage(frontmatter, body="Some lore body")
        vault_pages = [page]

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
            vault_pages=vault_pages,
            rolling_summary=None,
        )

        result = close_turn(conn, bundle, vault_service=vault_service)
        assert result.status == "complete"

        # Verify vault page written to master vault
        expected = vault_service.master_path / "lore" / "test_lore.md"
        assert expected.exists()
        # Verify player vault sync: gm_only page should not appear in player vault
        player_file = vault_service.player_vault_root / "lore" / "test_lore.md"
        assert not player_file.exists()


def test_close_turn_vault_write_failure_sets_needs_vault_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        vault_service = VaultService(
            campaign_id="c1",
            player_vault_root=tmp_path / "player_vault",
        )
        vault_service.ensure_master_path()
        vault_service.ensure_player_vault()

        # Create a page that will fail atomic_write
        frontmatter = LoreFrontmatter(
            id="bad_page",
            type="lore",
            name="Bad",
            aliases=[],
            visibility="gm_only",
            first_encountered="1",
            category="test",
        )
        page = VaultPage(frontmatter, body="bad")

        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
            vault_pages=[page],
            rolling_summary=None,
        )

        # Patch vault_service.write_page to raise
        def failing_write(self, page, rel_path, *, is_master=True):
            raise OSError("disk full")

        monkeypatch.setattr(VaultService, "write_page", failing_write)

        with pytest.raises(TrustServiceError, match="vault write failed"):
            close_turn(conn, bundle, vault_service=vault_service)

        # Turn status must be needs_vault_repair
        tr = TurnRecordRepository(conn)
        turn = tr.get("t1")
        assert turn is not None
        assert turn.status == "needs_vault_repair"
        assert turn.sync_warning is None


def test_close_turn_sync_failure_sets_sync_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)

        vault_service = VaultService(
            campaign_id="c1",
            player_vault_root=tmp_path / "player_vault",
        )
        vault_service.ensure_master_path()
        vault_service.ensure_player_vault()

        # Create a valid lore page that will be synced
        frontmatter = LoreFrontmatter(
            id="sync_lore",
            type="lore",
            name="Sync Lore",
            aliases=[],
            visibility="player_known",
            first_encountered="1",
            category="test",
        )
        page = VaultPage(frontmatter, body="Some body")
        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
            vault_pages=[page],
            rolling_summary=None,
        )

        # Patch VaultService.sync to raise an exception after vault writes complete
        def failing_sync(self):
            raise OSError("player vault unavailable")

        monkeypatch.setattr(VaultService, "sync", failing_sync)

        result = close_turn(conn, bundle, vault_service=vault_service)
        assert result.status == "complete"

        # sync_warning should be set on turn record
        tr = TurnRecordRepository(conn)
        turn = tr.get("t1")
        assert turn is not None
        assert turn.status == "complete"
        assert turn.sync_warning is not None
        assert "player vault unavailable" in turn.sync_warning


def test_close_turn_without_vault_service_skips_vault_operations(tmp_path: Path) -> None:
    path = _db(tmp_path)
    with campaign_db(path) as conn:
        apply_migrations(conn)
        bundle = TurnCloseBundle(
            turn_record=TurnRecord(
                turn_id="t1",
                campaign_id="c1",
                session_id="s1",
                status="complete",
                started_at="2026-04-26T12:00:00Z",
                completed_at="2026-04-26T12:00:00Z",
                schema_version=1,
            ),
            transcript_entries=[],
            roll_results=[],
            provider_logs=[],
            state_deltas=[],
            cost_logs=[],
            checkpoint_refs=[],
            vault_pages=[],
            rolling_summary=None,
        )
        # vault_service=None should work fine; no vault ops
        result = close_turn(conn, bundle, vault_service=None)
        assert result.status == "complete"
