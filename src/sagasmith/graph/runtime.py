"""GraphRuntime — owns persistence boundary writes for the SagaSmith graph.

Design decision (04-REVIEWS consensus): agent nodes stay pure. The runtime
wraps the compiled graph, and IT is the single caller of:
- SqliteSaver via the checkpointer compile option
- CheckpointRef writes (pre-narration and final)
- turn_close() at the end of a complete turn

Nodes accept AgentServices and return state dicts; they never touch SQLite.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sagasmith.graph.activation_log import AgentActivationLogger
from sagasmith.graph.checkpoints import (
    CheckpointKind,
    build_checkpointer,
    extract_checkpoint_id,
)
from sagasmith.graph.interrupts import InterruptEnvelope, InterruptKind
from sagasmith.persistence.repositories import CheckpointRefRepository, TurnRecordRepository
from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
from sagasmith.schemas.persistence import CheckpointRef, TurnRecord


def thread_config_for(campaign_id: str) -> dict[str, Any]:
    """Single source of truth for thread_id convention. D-ARB: campaign-scoped."""
    return {"configurable": {"thread_id": f"campaign:{campaign_id}"}}


@dataclass
class GraphRuntime:
    """Wraps a compiled persistent graph + database connection + activation logging."""

    graph: Any  # Compiled LangGraph
    db_conn: sqlite3.Connection
    campaign_id: str
    bootstrap: Any  # GraphBootstrap (untyped to avoid circular imports)

    @property
    def thread_config(self) -> dict[str, Any]:
        return thread_config_for(self.campaign_id)

    def invoke_turn(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Run the graph from START up to (but not including) orator.

        After the interrupt fires, writes a CheckpointRef(kind=pre_narration)
        row owned by this runtime. Returns the latest state values.

        Idempotent: if the thread is already at the orator interrupt or has
        already completed (next == () with values), returns immediately
        without re-running prior nodes.

        BudgetStopError raised inside any node is caught at the runtime
        boundary and translated to InterruptKind.BUDGET_STOP — nodes never
        see interrupt types.
        """
        from sagasmith.services.errors import BudgetStopError

        turn_id = initial_state["turn_id"]
        self._ensure_turn_record(initial_state)
        snapshot = self.graph.get_state(self.thread_config)
        snapshot_turn_id = (snapshot.values or {}).get("turn_id")
        if snapshot.next == ("orator",) and snapshot_turn_id == turn_id:
            return snapshot.values
        if snapshot.next == () and snapshot.values and snapshot_turn_id == turn_id:
            return snapshot.values
        try:
            _ = self.graph.invoke(initial_state, self.thread_config)
        except BudgetStopError as e:
            _ = self.post_interrupt(kind=InterruptKind.BUDGET_STOP, payload={"reason": str(e)})
            return self.graph.get_state(self.thread_config).values
        snapshot = self.graph.get_state(self.thread_config)
        if snapshot.next == ("orator",):
            self._record_pre_narration_checkpoint(turn_id, snapshot)
        return snapshot.values

    def post_interrupt(
        self, *, kind: InterruptKind, payload: dict[str, Any] | None = None
    ) -> InterruptEnvelope:
        """Write an interrupt envelope to the graph thread state.

        Uses LangGraph's native ``graph.update_state`` API. Single-slot
        semantics: a second call overwrites the first.
        """
        envelope = InterruptEnvelope.build(
            kind=kind,
            payload=payload,
            thread_id=self.thread_config["configurable"]["thread_id"],
        )
        self.graph.update_state(
            self.thread_config,
            {"last_interrupt": envelope.model_dump()},
            as_node="archivist",
        )
        return envelope

    def resume_after_interrupt(self, *, resume_payload: Any = None) -> dict[str, Any]:
        """Clear ``last_interrupt`` and resume the graph thread.

        Note: LangGraph 1.1.10 has a bug with Command(resume=None).
        Using None input directly is the working resume pattern proven in Task 1.
        """
        self.graph.update_state(
            self.thread_config,
            {"last_interrupt": None},
            as_node="archivist",
        )
        # resume_payload is accepted for API compatibility but not used
        # until LangGraph bug is fixed or we upgrade past 1.1.10.
        _ = resume_payload
        return self.graph.invoke(None, self.thread_config)

    def resume_and_close(
        self,
        turn_record: TurnRecord,
        *,
        transcript_entries=None,
        roll_results=None,
        provider_logs=None,
        state_deltas=None,
        cost_logs=None,
    ) -> TurnRecord:
        """Resume past the orator interrupt, run archivist, close the turn.

        Runtime builds the TurnCloseBundle with the final CheckpointRef and
        invokes `close_turn` (NOT the archivist node). Thin-node rule preserved.
        """
        # Note: LangGraph 1.1.10 has a bug with Command(resume=None).
        # Using None input directly is the working resume pattern proven in Task 1.
        _ = self.graph.invoke(None, self.thread_config)
        final_snapshot = self.graph.get_state(self.thread_config)
        final_cp_id = extract_checkpoint_id(final_snapshot)
        if final_cp_id is None:
            raise RuntimeError("LangGraph did not surface checkpoint_id after resume")

        final_ref = CheckpointRef(
            checkpoint_id=final_cp_id,
            turn_id=turn_record.turn_id,
            kind=CheckpointKind.FINAL.value,
            created_at=datetime.now(UTC).isoformat(),
        )
        bundle = TurnCloseBundle(
            turn_record=turn_record,
            transcript_entries=transcript_entries or [],
            roll_results=roll_results or [],
            provider_logs=provider_logs or [],
            state_deltas=state_deltas or [],
            cost_logs=cost_logs or [],
            checkpoint_refs=[final_ref],
        )
        return close_turn(self.db_conn, bundle)

    def _record_pre_narration_checkpoint(self, turn_id: str, snapshot) -> None:
        cp_id = extract_checkpoint_id(snapshot)
        if cp_id is None:
            raise RuntimeError("LangGraph did not surface checkpoint_id at orator interrupt")
        ref = CheckpointRef(
            checkpoint_id=cp_id,
            turn_id=turn_id,
            kind=CheckpointKind.PRE_NARRATION.value,
            created_at=datetime.now(UTC).isoformat(),
        )
        CheckpointRefRepository(self.db_conn).append(ref)
        self.db_conn.commit()

    def _ensure_turn_record(self, initial_state: dict[str, Any]) -> None:
        """Create the FK parent row needed before graph-side audit rows write."""
        turn_id = initial_state["turn_id"]
        if TurnRecordRepository(self.db_conn).get(turn_id) is not None:
            return

        now = datetime.now(UTC).isoformat()
        TurnRecordRepository(self.db_conn).upsert(
            TurnRecord(
                turn_id=turn_id,
                campaign_id=initial_state["campaign_id"],
                session_id=initial_state["session_id"],
                status="needs_vault_repair",
                started_at=now,
                completed_at=now,
                schema_version=1,
            )
        )
        self.db_conn.commit()


def build_persistent_graph(
    bootstrap, db_conn: sqlite3.Connection, campaign_id: str
) -> GraphRuntime:
    """Compile the graph with SqliteSaver + interrupt_before=[orator] + activation wrappers."""
    # Wrap each node with an activation logger. Re-bind bootstrap.
    wrapped = _wrap_bootstrap_with_logger(bootstrap, db_conn)
    # Build the graph structure, then recompile with checkpointer + interrupt_before.
    from langgraph.graph import END, START, StateGraph

    from sagasmith.graph.routing import route_by_phase
    from sagasmith.graph.state import SagaGraphState

    g = StateGraph(SagaGraphState)
    g.add_node("onboarding", wrapped.onboarding)
    g.add_node("oracle", wrapped.oracle)
    g.add_node("rules_lawyer", wrapped.rules_lawyer)
    g.add_node("orator", wrapped.orator)
    g.add_node("archivist", wrapped.archivist)
    g.add_conditional_edges(
        START,
        route_by_phase,
        {"onboarding": "onboarding", "oracle": "oracle", END: END},
    )
    g.add_edge("oracle", "rules_lawyer")
    g.add_edge("rules_lawyer", "orator")
    g.add_edge("orator", "archivist")
    g.add_edge("archivist", END)
    g.add_edge("onboarding", END)
    compiled = g.compile(
        checkpointer=build_checkpointer(db_conn),
        interrupt_before=["orator"],
    )
    return GraphRuntime(
        graph=compiled,
        db_conn=db_conn,
        campaign_id=campaign_id,
        bootstrap=wrapped,
    )


def _wrap_bootstrap_with_logger(bootstrap, db_conn: sqlite3.Connection):
    """Return a GraphBootstrap whose node callables are wrapped with AgentActivationLogger."""
    from sagasmith.graph.bootstrap import GraphBootstrap

    def _wrap(node_fn, agent_name):
        def wrapped(state, *args, **kwargs):
            turn_id = state["turn_id"]
            with AgentActivationLogger(
                db_conn, turn_id=turn_id, agent_name=agent_name
            ):
                return node_fn(state, *args, **kwargs)

        return wrapped

    return GraphBootstrap(
        services=bootstrap.services,
        onboarding=_wrap(bootstrap.onboarding, "onboarding"),
        oracle=_wrap(bootstrap.oracle, "oracle"),
        rules_lawyer=_wrap(bootstrap.rules_lawyer, "rules_lawyer"),
        orator=_wrap(bootstrap.orator, "orator"),
        archivist=_wrap(bootstrap.archivist, "archivist"),
    )
