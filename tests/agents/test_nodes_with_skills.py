"""Tests for agent node set_skill wiring via contextvar handoff.

Covers:
- oracle, rules_lawyer, orator, archivist, onboarding set_skill calls
- rules_lawyer load_skill on trigger match
- graceful degradation when no activation logger or skill_store
- end-to-end first_slice_only play turn with skill_name assertions
"""

from __future__ import annotations

import sqlite3

import pytest

from sagasmith.agents.archivist.node import archivist_node
from sagasmith.agents.onboarding.node import onboarding_node
from sagasmith.agents.oracle.node import oracle_node
from sagasmith.agents.orator.node import orator_node
from sagasmith.agents.rules_lawyer.node import rules_lawyer_node
from sagasmith.evals.fixtures import (
    make_valid_character_sheet,
    make_valid_content_policy,
    make_valid_house_rules,
    make_valid_saga_state,
    make_valid_session_state,
)
from sagasmith.graph.bootstrap import AgentServices, GraphBootstrap, default_skill_store
from sagasmith.graph.runtime import build_persistent_graph
from sagasmith.persistence.migrations import apply_migrations
from sagasmith.persistence.repositories import AgentSkillLogRepository
from sagasmith.schemas.persistence import TurnRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.dice import DiceService
from sagasmith.skills_adapter import SkillStore


@pytest.fixture
def production_skill_store():
    return default_skill_store()


@pytest.fixture
def empty_skill_store():
    return SkillStore(roots=[])


@pytest.fixture
def services_with_skills(production_skill_store):
    return AgentServices(
        dice=DiceService(campaign_seed="test", session_seed="s1"),
        cost=CostGovernor(session_budget_usd=1.0),
        safety=None,
        llm=None,
        skill_store=production_skill_store,
    )


def _make_conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:", check_same_thread=False)


def _insert_campaign_and_turn(conn: sqlite3.Connection, *, status: str = "complete") -> None:
    conn.execute(
        "INSERT INTO campaigns (campaign_id, campaign_name, campaign_slug, created_at, sagasmith_version, manifest_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("cmp_001", "Test", "test", "2026-01-01T00:00:00Z", "0.0.1", 1),
    )
    conn.execute(
        "INSERT INTO turn_records (turn_id, campaign_id, session_id, status, started_at, completed_at, schema_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("turn_000001", "cmp_001", "sess_001", status, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", 1),
    )
    conn.commit()


def _play_state(**overrides):
    base = {
        "campaign_id": "cmp_001",
        "session_id": "sess_001",
        "turn_id": "turn_000001",
        "phase": "play",
        "player_profile": None,
        "content_policy": None,
        "house_rules": None,
        "world_bible": None,
        "campaign_seed": None,
        "character_sheet": None,
        "session_state": {
            "current_scene_id": None,
            "current_location_id": None,
            "active_quest_ids": [],
            "in_game_clock": {"day": 1, "hour": 12, "minute": 0},
            "turn_count": 0,
            "transcript_cursor": None,
            "last_checkpoint_id": None,
        },
        "combat_state": None,
        "pending_player_input": "roll perception",
        "memory_packet": None,
        "scene_brief": None,
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
    }
    base.update(overrides)
    return base


class TestOracleSetSkill:
    def test_oracle_skill_name_logged(self, production_skill_store):
        """Test 1: oracle node sets skill_name during persistent graph run."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        oracle_rows = [r for r in rows if r.agent_name == "oracle"]
        assert len(oracle_rows) == 1
        assert oracle_rows[0].skill_name == "scene-brief-composition"


class TestRulesLawyerSetSkill:
    def test_trigger_match_sets_skill(self, production_skill_store):
        """Test 2: trigger match calls load_skill and sets skill-check-resolution."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state(pending_player_input="roll perception")
        runtime.invoke_turn(state)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        rl_rows = [r for r in rows if r.agent_name == "rules_lawyer"]
        assert len(rl_rows) == 1
        assert rl_rows[0].skill_name == "skill-check-resolution"

    def test_no_match_no_skill(self, production_skill_store):
        """Test 3: no trigger match leaves skill_name NULL."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state(pending_player_input="hello world")
        runtime.invoke_turn(state)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        rl_rows = [r for r in rows if r.agent_name == "rules_lawyer"]
        assert len(rl_rows) == 1
        assert rl_rows[0].skill_name is None


class TestOratorSetSkill:
    def test_orator_skill_name_logged(self, production_skill_store):
        """Test 4: orator node sets scene-rendering skill."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)
        turn_record = TurnRecord(
            turn_id="turn_000001",
            campaign_id="cmp_001",
            session_id="sess_001",
            status="needs_vault_repair",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:00Z",
            schema_version=1,
        )
        runtime.resume_and_close(turn_record)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        orator_rows = [r for r in rows if r.agent_name == "orator"]
        assert len(orator_rows) == 1
        assert orator_rows[0].skill_name == "scene-rendering"


class TestArchivistSetSkill:
    def test_archivist_skill_name_logged(self, production_skill_store):
        """Test 5: archivist node sets memory-packet-assembly skill."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)
        turn_record = TurnRecord(
            turn_id="turn_000001",
            campaign_id="cmp_001",
            session_id="sess_001",
            status="needs_vault_repair",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:00Z",
            schema_version=1,
        )
        runtime.resume_and_close(turn_record)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        arch_rows = [r for r in rows if r.agent_name == "archivist"]
        assert len(arch_rows) >= 1
        skill_names = {r.skill_name for r in arch_rows}
        # Archivist activates 3 skills; activation log records the last one
        assert len(skill_names & {"vault-page-upsert", "memory-packet-assembly", "entity-resolution"}) >= 1


class TestOnboardingSetSkill:
    def test_onboarding_skill_name_logged(self, production_skill_store):
        """Test 6: onboarding node sets onboarding-phase-wizard skill on incomplete profile."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(
            dice=dice, cost=cost, skill_store=production_skill_store
        )
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state(phase="onboarding", player_profile=None)
        runtime.invoke_turn(state)

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        onb_rows = [r for r in rows if r.agent_name == "onboarding"]
        assert len(onb_rows) == 1
        assert onb_rows[0].skill_name == "onboarding-phase-wizard"


class TestGracefulOutsideActivation:
    def test_oracle_node_no_activation_no_crash(self, empty_skill_store):
        """Test 7: calling oracle_node directly outside logger context is safe."""
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=empty_skill_store,
        )
        state = make_valid_saga_state(scene_brief=None).model_dump()
        result = oracle_node(state, services)
        assert result.get("scene_brief") is not None

    def test_rules_lawyer_node_no_activation_no_crash(self, empty_skill_store):
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=empty_skill_store,
        )
        state = make_valid_saga_state(
            pending_player_input="roll perception",
            character_sheet=make_valid_character_sheet(),
            check_results=[],
        ).model_dump()
        result = rules_lawyer_node(state, services)
        assert "check_results" in result

    def test_orator_node_no_activation_no_crash(self, empty_skill_store):
        from sagasmith.schemas.narrative import SceneBrief

        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=empty_skill_store,
        )
        brief = SceneBrief(
            scene_id="s1",
            intent="x",
            location=None,
            present_entities=[],
            beats=[],
            success_outs=[],
            failure_outs=[],
            pacing_target={"pillar": "exploration", "tension": "low", "length": "short"},  # type: ignore[arg-type]
        )
        state = make_valid_saga_state(
            scene_brief=brief,
            pending_narration=[],
        ).model_dump()
        result = orator_node(state, services)
        assert "pending_narration" in result

    def test_archivist_node_no_activation_no_crash(self, empty_skill_store):
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=empty_skill_store,
        )
        state = make_valid_saga_state(
            session_state=make_valid_session_state(turn_count=0),
            pending_player_input="look",
            pending_narration=["line"],
        ).model_dump()
        result = archivist_node(state, services)
        session_state = result["session_state"]
        assert isinstance(session_state, dict)
        assert session_state["turn_count"] == 1

    def test_onboarding_node_no_activation_no_crash(self, empty_skill_store):
        services = AgentServices(
            dice=DiceService(campaign_seed="t", session_seed="s"),
            cost=CostGovernor(session_budget_usd=1.0),
            skill_store=empty_skill_store,
        )
        state = make_valid_saga_state(
            player_profile=None,
            content_policy=make_valid_content_policy(),
            house_rules=make_valid_house_rules(),
        ).model_dump()
        result = onboarding_node(state, services)
        assert result == {"phase": "onboarding"}


class TestEndToEndFirstSliceOnly:
    def test_full_turn_with_first_slice_only(self):
        """Test 8: first_slice_only=True store completes a full play turn."""
        conn = _make_conn()
        apply_migrations(conn)
        _insert_campaign_and_turn(conn)

        store = default_skill_store(first_slice_only=True)
        dice = DiceService(campaign_seed="t", session_seed="s")
        cost = CostGovernor(session_budget_usd=1.0)
        bootstrap = GraphBootstrap.from_services(dice=dice, cost=cost, skill_store=store)
        runtime = build_persistent_graph(bootstrap, conn, campaign_id="cmp_001")

        state = _play_state()
        runtime.invoke_turn(state)

        turn_record = TurnRecord(
            turn_id="turn_000001",
            campaign_id="cmp_001",
            session_id="sess_001",
            status="needs_vault_repair",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:00Z",
            schema_version=1,
        )
        completed = runtime.resume_and_close(turn_record)
        assert completed.status == "complete"

        rows = AgentSkillLogRepository(conn).list_for_turn("turn_000001")
        skill_by_agent = {r.agent_name: r.skill_name for r in rows}
        assert skill_by_agent.get("oracle") == "scene-brief-composition"
        assert skill_by_agent.get("rules_lawyer") == "skill-check-resolution"
        assert skill_by_agent.get("orator") == "scene-rendering"
        assert skill_by_agent.get("archivist") == "memory-packet-assembly"

        # Phase 6 memory-packet-assembly is first-slice safe and provider-free.
        assert store.find(name="memory-packet-assembly", agent_scope="archivist") is not None
