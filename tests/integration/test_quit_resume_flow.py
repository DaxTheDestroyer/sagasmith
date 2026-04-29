"""End-to-end quit/resume lifecycle integration tests.

QA-06 (player-vault GM leakage) is covered in tests/vault/test_player_projection.py.
This file covers:
  - Full quit/resume cycle: play 3 turns, post SESSION_END, verify vault sync
    and that next session number increments and memory packet includes entities
    from earlier sessions via FTS5/NetworkX retrieval within token cap.
  - Resume after pre-narration interrupt (retry path) — covered by existing
    tests in tests/integration/test_narration_recovery.py; included here as
    a lightweight smoke to ensure checkpoint survival.
"""

from __future__ import annotations

from pathlib import Path

from sagasmith.app.campaign import init_campaign
from sagasmith.evals.fixtures import (
    make_valid_campaign_seed,
    make_valid_character_sheet,
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_player_profile,
    make_valid_scene_brief,
    make_valid_session_state,
    make_valid_world_bible,
)
from sagasmith.graph.bootstrap import GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.db import open_campaign_db
from sagasmith.persistence.repositories import TurnRecordRepository
from sagasmith.providers import DeterministicFakeClient
from sagasmith.schemas.enums import InterruptKind
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.tui.runtime import build_app
from sagasmith.vault import VaultService


def _base_state_values(manifest, service):
    """Reusable fixture objects for player state."""
    return {
        "profile": make_valid_player_profile().model_dump(mode="json"),
        "content_policy": make_valid_content_policy().model_dump(mode="json"),
        "house_rules": make_valid_house_rules().model_dump(mode="json"),
        "character_sheet": make_valid_character_sheet().model_dump(mode="json"),
        "session_state": make_valid_session_state().model_dump(mode="json"),
        "world_bible": make_valid_world_bible().model_dump(mode="json"),
        "campaign_seed": make_valid_campaign_seed().model_dump(mode="json"),
        "vault_master_path": str(service.master_path),
        "vault_player_path": str(service.player_vault_root),
    }


def test_full_quit_resume_cycle(tmp_path: Path) -> None:
    """Play 3 turns, post SESSION_END, verify vault sync and session increment."""
    # --- Setup campaign and runtime ---
    root = tmp_path / "rivermouth"
    manifest = init_campaign(name="QuitResumeTest", root=root, provider="fake")
    conn = open_campaign_db(root / "campaign.sqlite")

    service = VaultService(
        campaign_id=manifest.campaign_id, player_vault_root=root / "player_vault"
    )

    # Deterministic fake LLM client that provides rolling summary updates only.
    from sagasmith.evals.fixtures import make_fake_llm_response

    client = DeterministicFakeClient(
        scripted_responses={
            "archivist.rolling_summary_update": make_fake_llm_response(
                agent_name="archivist.rolling_summary_update",
                text="Rolling summary updated with latest events.",
            )
        }
    )

    dice = DiceService(campaign_seed=manifest.campaign_id, session_seed="session_001")
    cost = CostGovernor(session_budget_usd=1.0)
    bootstrap = GraphBootstrap.from_services(
        dice=dice,
        cost=cost,
        llm=client,
        skill_store=default_skill_store(),
        transcript_conn=conn,
        vault_service=service,
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id=manifest.campaign_id)

    base_vals = _base_state_values(manifest, service)

    # Scene brief template — we vary scene_id each turn to force scene boundary
    base_scene = make_valid_scene_brief().model_dump(mode="json")

    def make_scene(turn_num: int) -> dict:
        s = base_scene.copy()
        s["scene_id"] = f"scene_{turn_num:03d}"
        return s

    # Helper: build state for a given turn
    def build_state(
        turn_num: int,
        prev_state: dict | None,
        session_id: str = "session_001",
        scene_override: dict | None = None,
    ) -> dict:
        turn_id = f"turn_{turn_num:06d}"
        if prev_state is None:
            return {
                "campaign_id": manifest.campaign_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "play",
                "player_profile": base_vals["profile"],
                "content_policy": base_vals["content_policy"],
                "house_rules": base_vals["house_rules"],
                "character_sheet": base_vals["character_sheet"],
                "session_state": base_vals["session_state"].copy(),
                "combat_state": None,
                "pending_player_input": f"Turn {turn_num} action",
                "memory_packet": None,
                "scene_brief": scene_override or make_scene(turn_num),
                "resolved_beat_ids": [],
                "oracle_bypass_detected": False,
                "check_results": [],
                "state_deltas": [],
                "pending_conflicts": [],
                "pending_narration": [],
                "safety_events": [],
                "cost_state": {
                    "session_budget_usd": 1.0,
                    "spent_usd_estimate": 0.0,
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "unknown_cost_call_count": 0,
                    "warnings_sent": [],
                    "hard_stopped": False,
                },
                "last_interrupt": None,
                "vault_master_path": base_vals["vault_master_path"],
                "vault_player_path": base_vals["vault_player_path"],
                "rolling_summary": None,
                "world_bible": base_vals["world_bible"],
                "campaign_seed": base_vals["campaign_seed"],
            }
        # Evolve from previous state; keep durable fields but reset turn-specific ones
        state = prev_state.copy()
        state.update(
            turn_id=turn_id,
            pending_player_input=f"Turn {turn_num} action",
            memory_packet=None,
            pending_narration=[],
            safety_events=[],
            last_interrupt=None,
            scene_brief=scene_override or make_scene(turn_num),
        )
        return state

    try:
        # --- Turn 1 ---
        state1 = build_state(1, None)
        runtime.invoke_turn(state1)
        tr1 = TurnRecordRepository(conn).get(state1["turn_id"])
        assert tr1 is not None and tr1.status == "needs_vault_repair"
        completed1 = runtime.resume_and_close(tr1)
        assert completed1.status == "complete"
        snap1 = runtime.graph.get_state(runtime.thread_config)
        state_after_1 = snap1.values or {}

        # --- Turn 2 ---
        state2 = build_state(2, state_after_1)
        runtime.invoke_turn(state2)
        tr2 = TurnRecordRepository(conn).get(state2["turn_id"])
        completed2 = runtime.resume_and_close(tr2)
        assert completed2.status == "complete"
        snap2 = runtime.graph.get_state(runtime.thread_config)
        state_after_2 = snap2.values or {}

        # --- Turn 3 (session end) ---
        state3 = build_state(3, state_after_2)
        runtime.invoke_turn(state3)
        # Post SESSION_END before closing turn 3
        runtime.post_interrupt(kind=InterruptKind.SESSION_END, payload={"reason": "player quit"})
        tr3 = TurnRecordRepository(conn).get(state3["turn_id"])
        completed3 = runtime.resume_and_close(tr3)
        assert completed3.status == "complete"

        # --- Verify post-session state ---
        # Player vault exists and contains pages derived from master vault
        assert (service.player_vault_root / "index.md").exists()
        assert (service.player_vault_root / "log.md").exists()
        # Present entity from scene_brief should have created an NPC page in player vault
        npc_path = service.player_vault_root / "npcs" / "npc_mira_warden.md"
        assert npc_path.exists(), "Expected NPC page missing from player vault"
        # Verify session page authored in master vault
        session_page = service.master_path / "sessions" / "session_001.md"
        assert session_page.exists(), "Session page not authored"
        # No sync warning in turn_record
        cur = conn.execute(
            "SELECT sync_warning FROM turn_records WHERE turn_id = ?", (state3["turn_id"],)
        )
        row = cur.fetchone()
        assert row is None or row[0] is None, f"Unexpected sync_warning: {row}"

        # --- Close old runtime ---
        conn.close()

        # --- Re-open campaign ---
        new_app = build_app(root)
        assert new_app.current_session_id == "session_002"
        new_runtime = new_app.graph_runtime

        # Baseline snapshot should have rolling_summary from previous session
        init_snap = new_runtime.graph.get_state(new_runtime.thread_config)
        init_state = init_snap.values or {}
        rolling = init_state.get("rolling_summary")
        assert isinstance(rolling, str) and len(rolling) > 0, "Missing rolling summary"

        # --- Turn 4 (new session) ---
        turn4_state = {
            "campaign_id": manifest.campaign_id,
            "session_id": new_app.current_session_id,
            "turn_id": "turn_000004",
            "phase": "play",
            "player_profile": base_vals["profile"],
            "content_policy": base_vals["content_policy"],
            "house_rules": base_vals["house_rules"],
            "character_sheet": base_vals["character_sheet"],
            "session_state": {
                "session_number": new_app.current_session_number,
                "turn_count": 0,
                "current_scene_id": None,
                "current_location_id": None,
                "active_quest_ids": [],
                "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
                "transcript_cursor": None,
                "last_checkpoint_id": None,
            },
            "combat_state": None,
            "pending_player_input": "Begin session 2",
            "memory_packet": None,
            "scene_brief": make_scene(4),  # fresh scene
            "resolved_beat_ids": [],
            "oracle_bypass_detected": False,
            "check_results": [],
            "state_deltas": [],
            "pending_conflicts": [],
            "pending_narration": [],
            "safety_events": [],
            "cost_state": {
                "session_budget_usd": 1.0,
                "spent_usd_estimate": 0.0,
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "unknown_cost_call_count": 0,
                "warnings_sent": [],
                "hard_stopped": False,
            },
            "last_interrupt": None,
            "vault_master_path": base_vals["vault_master_path"],
            "vault_player_path": base_vals["vault_player_path"],
            "rolling_summary": rolling,  # carry forward from previous session
            "world_bible": base_vals["world_bible"],
            "campaign_seed": base_vals["campaign_seed"],
        }
        values4 = new_runtime.invoke_turn(turn4_state)
        mp = values4.get("memory_packet")
        assert mp is not None, "MemoryPacket missing after turn 4"

        # Ensure entities from earlier session (e.g., npc_mira_warden) are present
        entity_ids = [e["entity_id"] for e in mp["entities"]]
        assert any("mira_warden" in eid for eid in entity_ids), (
            f"Expected entity 'mira_warden' not in memory entities: {entity_ids}"
        )

        # Token cap respect (default 2048)
        from sagasmith.schemas.common import estimate_tokens

        summary_tokens = estimate_tokens(mp["summary"])
        turns_tokens = sum(estimate_tokens(t) for t in mp["recent_turns"])
        total_tokens = summary_tokens + turns_tokens
        assert total_tokens <= 2048, f"MemoryPacket exceeds token cap ({total_tokens} > 2048)"

        # Retrieval notes should show FTS5/graph activity
        assert len(mp["retrieval_notes"]) > 0

    finally:
        # Clean up connections
        try:
            conn.close()
        except Exception:
            pass
        try:
            if "new_app" in locals() and new_app._service_conn:
                new_app._service_conn.close()
        except Exception:
            pass


def test_resume_after_pre_narration_crash(tmp_path: Path) -> None:
    """Simple smoke: after pre-narration checkpoint, retry_narration completes."""
    # This is a minimal version of the comprehensive tests in test_narration_recovery.
    # It confirms the retry path is intact.
    from sagasmith.graph.checkpoints import CheckpointKind
    from sagasmith.persistence.repositories import CheckpointRefRepository

    root = tmp_path / "retry_campaign"
    manifest = init_campaign(name="RetryTest", root=root, provider="fake")
    conn = open_campaign_db(root / "campaign.sqlite")

    service = VaultService(campaign_id=manifest.campaign_id, player_vault_root=root / "player_vault")
    bootstrap = GraphBootstrap.from_services(
        dice=DiceService(campaign_seed="x", session_seed="y"),
        cost=CostGovernor(session_budget_usd=1.0),
        vault_service=service,
        transcript_conn=conn,
    )
    runtime = build_persistent_graph(bootstrap, conn, campaign_id=manifest.campaign_id)

    # Minimal play state
    state = {
        "campaign_id": manifest.campaign_id,
        "session_id": "session_001",
        "turn_id": "turn_000001",
        "phase": "play",
        "player_profile": None,
        "content_policy": None,
        "house_rules": None,
        "character_sheet": None,
        "session_state": {
            "session_number": 1,
            "turn_count": 0,
            "current_scene_id": None,
            "current_location_id": None,
            "active_quest_ids": [],
            "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
            "transcript_cursor": None,
            "last_checkpoint_id": None,
        },
        "combat_state": None,
        "pending_player_input": "test",
        "memory_packet": None,
        "scene_brief": None,
        "resolved_beat_ids": [],
        "oracle_bypass_detected": False,
        "check_results": [],
        "state_deltas": [],
        "pending_conflicts": [],
        "pending_narration": [],
        "safety_events": [],
        "cost_state": {
            "session_budget_usd": 1.0,
            "spent_usd_estimate": 0.0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "unknown_cost_call_count": 0,
            "warnings_sent": [],
            "hard_stopped": False,
        },
        "last_interrupt": None,
        "vault_master_path": str(service.master_path),
        "vault_player_path": str(service.player_vault_root),
        "rolling_summary": None,
        "world_bible": None,
        "campaign_seed": None,
    }

    runtime.invoke_turn(state)

    # Pre-narration checkpoint must exist
    snapshot = runtime.graph.get_state(runtime.thread_config)
    assert snapshot.next == ("orator",), "Expected interrupt before orator"

    # Retry the narration (this will re-run orator + archivist and close the turn)
    retry_values = runtime.retry_narration("turn_000001")

    # The turn should now be complete (status filled by retry_narration -> resume_and_close)
    turn = TurnRecordRepository(conn).get("turn_000001")
    assert turn is not None and turn.status == "retried"

    # Pre-narration checkpoint should still be present (not duplicated)
    refs = CheckpointRefRepository(conn).list_for_turn("turn_000001")
    pre_refs = [r for r in refs if r.kind == CheckpointKind.PRE_NARRATION.value]
    assert len(pre_refs) >= 1, "pre_narration checkpoint missing after retry"

    # Memory_packet must be populated by archivist
    assert retry_values.get("memory_packet") is not None

    # Clean up
    conn.close()
