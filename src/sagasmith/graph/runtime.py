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
from sagasmith.graph.interrupts import InterruptEnvelope, InterruptKind, is_session_end_state
from sagasmith.persistence.repositories import CheckpointRefRepository, TurnRecordRepository
from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
from sagasmith.schemas.persistence import CheckpointRef, TurnRecord
from sagasmith.vault import VaultPage


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
        if snapshot.next == () and snapshot.values and snapshot_turn_id != turn_id:
            from langgraph.graph import START

            self.graph.update_state(self.thread_config, initial_state, as_node=START)
        try:
            _ = self.graph.invoke(initial_state, self.thread_config)
        except BudgetStopError as e:
            _ = self.post_interrupt(kind=InterruptKind.BUDGET_STOP, payload={"reason": str(e)})
            return self.graph.get_state(self.thread_config).values
        snapshot = self.graph.get_state(self.thread_config)
        if (snapshot.values or {}).get("turn_id") != turn_id:
            return self._pre_narration_fallback_state(initial_state)
        if (snapshot.values or {}).get("memory_packet") is None:
            return self._pre_narration_fallback_state({**initial_state, **(snapshot.values or {})})
        if snapshot.next == ("orator",):
            self._record_pre_narration_checkpoint(turn_id, snapshot)
        return snapshot.values

    def _pre_narration_fallback_state(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Return pre-narration state when an ended LangGraph thread will not restart.

        LangGraph 1.1.x can retain an END checkpoint for a campaign-scoped thread
        after process restart. This preserves the Phase 7 resume contract by
        assembling the provider-free memory packet from persisted vault/transcript
        layers for the new turn.
        """
        from sagasmith.agents.archivist.skills.memory_packet_assembly.logic import (
            assemble_memory_packet,
        )

        vault_service = getattr(self.bootstrap.services, "vault_service", None)
        memory_packet = assemble_memory_packet(
            initial_state,
            conn=self.db_conn,
            vault_service=vault_service,
        )
        return {**initial_state, "memory_packet": memory_packet.model_dump()}

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
        vault_pages=None,
        rolling_summary=None,
    ) -> TurnRecord:
        """Resume past the orator interrupt, run archivist, close the turn.

        Runtime builds the TurnCloseBundle with the final CheckpointRef and
        invokes `close_turn` (NOT the archivist node). Thin-node rule preserved.
        """
        # Note: LangGraph 1.1.10 has a bug with Command(resume=None).
        # Using None input directly is the working resume pattern proven in Task 1.
        initial_snapshot = self.graph.get_state(self.thread_config)
        initial_state = initial_snapshot.values or {}
        session_end_requested = is_session_end_state(initial_state)
        _ = self.graph.invoke(None, self.thread_config)
        final_snapshot = self.graph.get_state(self.thread_config)
        final_cp_id = extract_checkpoint_id(final_snapshot)
        if final_cp_id is None:
            raise RuntimeError("LangGraph did not surface checkpoint_id after resume")

        # Collect vault_pending_writes from final state (produced by archivist_node)
        final_state = final_snapshot.values or {}
        session_end_requested = session_end_requested or is_session_end_state(final_state)
        vault_pages_raw = vault_pages or final_state.get("vault_pending_writes", [])
        # Deserialize VaultPage objects if stored as dicts for checkpoint compatibility.
        vault_pages_list: list[VaultPage] = []
        for item in vault_pages_raw:
            if isinstance(item, VaultPage):
                vault_pages_list.append(item)
            elif isinstance(item, dict):
                # Reconstruct from serialized form
                vault_pages_list.append(VaultPage.from_dict(item))
        if rolling_summary is None:
            rolling_summary_val = final_state.get("rolling_summary")
            if isinstance(rolling_summary_val, str):
                rolling_summary = rolling_summary_val

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
            vault_pages=vault_pages_list,
            rolling_summary=rolling_summary,
        )
        # Inject vault_service if available
        vault_service = getattr(self.bootstrap.services, "vault_service", None)
        completed_record = close_turn(self.db_conn, bundle, vault_service=vault_service)
        if session_end_requested and vault_service is not None:
            _author_session_after_close(
                db_conn=self.db_conn,
                campaign_id=self.campaign_id,
                session_id=turn_record.session_id,
                final_state=final_state,
                vault_service=vault_service,
            )
        return completed_record

    def discard_incomplete_turn(self, turn_id: str) -> TurnRecord:
        """Rewind the graph thread to the pre-narration checkpoint and mark the
        turn as ``discarded``.

        Raises ``ValueError`` if no pre-narration checkpoint exists for the turn.
        """
        repo = CheckpointRefRepository(self.db_conn)
        refs = [
            r for r in repo.list_for_turn(turn_id) if r.kind == CheckpointKind.PRE_NARRATION.value
        ]
        if not refs:
            raise ValueError(f"No pre_narration checkpoint for turn {turn_id}")

        pre_narration_ref = refs[-1]  # most recent pre_narration
        self._rewind_to_checkpoint(pre_narration_ref.checkpoint_id)

        now = datetime.now(UTC).isoformat()
        turn_repo = TurnRecordRepository(self.db_conn)
        existing = turn_repo.get(turn_id)
        if existing is None:
            raise ValueError(f"No TurnRecord for turn {turn_id}")

        discarded = TurnRecord(
            turn_id=existing.turn_id,
            campaign_id=existing.campaign_id,
            session_id=existing.session_id,
            status="discarded",
            started_at=existing.started_at,
            completed_at=now,
            schema_version=existing.schema_version,
        )
        turn_repo.upsert(discarded)
        self.db_conn.commit()
        return discarded

    def retry_narration(self, turn_id: str) -> dict[str, Any]:
        """Rewind to the pre-narration checkpoint, clear pending narration, and
        re-invoke orator + archivist.

        Returns the final graph state values after the retry completes.

        Deterministic invariant: check_results, dice outcomes, and HP/state are
        byte-identical to a non-retried run because the pre-narration snapshot
        freezes all mechanical state before the orator begins.

        Raises ``ValueError`` if no pre-narration checkpoint exists for the turn.
        """
        repo = CheckpointRefRepository(self.db_conn)
        refs = [
            r for r in repo.list_for_turn(turn_id) if r.kind == CheckpointKind.PRE_NARRATION.value
        ]
        if not refs:
            raise ValueError(f"No pre_narration checkpoint for turn {turn_id}")

        pre_narration_ref = refs[-1]
        self._rewind_to_checkpoint(pre_narration_ref.checkpoint_id, clear_pending_narration=True)

        # Mark the turn record as retried (for audit trail).
        turn_repo = TurnRecordRepository(self.db_conn)
        existing = turn_repo.get(turn_id)
        if existing is not None:
            now = datetime.now(UTC).isoformat()
            retried = TurnRecord(
                turn_id=existing.turn_id,
                campaign_id=existing.campaign_id,
                session_id=existing.session_id,
                status="retried",
                started_at=existing.started_at,
                completed_at=now,
                schema_version=existing.schema_version,
            )
            turn_repo.upsert(retried)
            self.db_conn.commit()

        # Re-invoke past the orator interrupt through archivist.
        # After rewind the graph is paused at orator; invoke(None) runs orator → archivist → END.
        _ = self.graph.invoke(None, self.thread_config)
        return self.graph.get_state(self.thread_config).values

    def preview_retcon(self, selected_turn_id: str):
        """Preview a checkpoint-backed retcon for a completed canonical turn."""
        from sagasmith.persistence.retcon import RetconService

        return RetconService(self.db_conn, campaign_id=self.campaign_id).preview(selected_turn_id)

    def confirm_retcon(
        self,
        selected_turn_id: str,
        confirmation_token: str,
        *,
        reason: str = "player_retcon",
    ):
        """Confirm a retcon, rewind to the prior checkpoint, and rebuild derived layers."""
        from sagasmith.memory.fts5 import FTS5Index
        from sagasmith.memory.graph import reset_vault_graph_cache, warm_vault_graph
        from sagasmith.persistence.retcon import RetconBlockedError, RetconService

        service = RetconService(self.db_conn, campaign_id=self.campaign_id)
        result = service.confirm(
            selected_turn_id,
            confirmation_token,
            reason=reason,
        )
        try:
            self._rewind_to_checkpoint(result.prior_checkpoint_id)
            vault_service = getattr(self.bootstrap.services, "vault_service", None)
            if vault_service is not None:
                master_path = vault_service.master_path
                FTS5Index(self.db_conn).rebuild_all(master_path)
                reset_vault_graph_cache()
                warm_vault_graph(master_path)
                rebuild_indices = getattr(vault_service, "rebuild_indices", None)
                if callable(rebuild_indices):
                    rebuild_indices(self.db_conn)
                vault_service.sync()
        except Exception as exc:
            raise RetconBlockedError(
                "Retcon status was committed but rollback repair did not fully complete.",
                (
                    "Repair by running vault rebuild/sync and checkpoint repair before continuing. "
                    f"Original error: {exc}"
                ),
            ) from exc
        return result

    def _rewind_to_checkpoint(
        self, checkpoint_id: str, *, clear_pending_narration: bool = False
    ) -> None:
        """Fork the thread from a specific checkpoint.

        Uses LangGraph's ``update_state`` with a ``checkpoint_id`` to create a
        new branch point at the target snapshot.  The thread's head advances to
        this forked checkpoint so the next ``invoke`` continues from here.

        If *clear_pending_narration* is ``True``, the ``pending_narration``
        field is reset to ``[]`` in the forked state (defensive — the
        pre-narration snapshot should already have it empty).
        """
        rewind_config: dict[str, Any] = {
            "configurable": {
                "thread_id": self.thread_config["configurable"]["thread_id"],
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            }
        }
        updates: dict[str, Any] = {}
        if clear_pending_narration:
            updates["pending_narration"] = []
        self.graph.update_state(rewind_config, updates if updates else None)

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
    if getattr(bootstrap.services, "transcript_conn", None) is None:
        object.__setattr__(bootstrap.services, "transcript_conn", db_conn)
    # Wrap each node with an activation logger. Re-bind bootstrap.
    wrapped = _wrap_bootstrap_with_logger(bootstrap, db_conn)
    # Build the graph structure, then recompile with checkpointer + interrupt_before.
    from langgraph.graph import END, START, StateGraph

    from sagasmith.graph.routing import route_after_oracle, route_by_phase
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
        {"onboarding": "onboarding", "oracle": "oracle", "rules_lawyer": "rules_lawyer", END: END},
    )
    g.add_conditional_edges(
        "oracle", route_after_oracle, {"rules_lawyer": "rules_lawyer", END: END}
    )
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


def _author_session_after_close(
    *,
    db_conn: sqlite3.Connection,
    campaign_id: str,
    session_id: str,
    final_state: dict[str, Any],
    vault_service: Any,
) -> None:
    from sagasmith.agents.archivist.skills.session_page_authoring.logic import author_session

    session_number = _session_number_from_id(session_id)
    if session_number is None:
        return
    date_in_game = str(final_state.get("game_clock", "unknown"))
    author_session(
        session_number=session_number,
        campaign_id=campaign_id,
        db_conn=db_conn,
        vault_service=vault_service,
        date_in_game=date_in_game,
    )
    vault_service.resolver.refresh()
    vault_service.rebuild_indices(db_conn)
    vault_service.sync()


def _session_number_from_id(session_id: str) -> int | None:
    prefix, sep, suffix = session_id.rpartition("_")
    if sep and prefix == "session" and suffix.isdigit():
        return int(suffix)
    return None


def _wrap_bootstrap_with_logger(bootstrap, db_conn: sqlite3.Connection):
    """Return a GraphBootstrap whose node callables are wrapped with AgentActivationLogger."""
    from sagasmith.graph.bootstrap import GraphBootstrap

    def _wrap(node_fn, agent_name):
        def wrapped(state, *args, **kwargs):
            turn_id = state["turn_id"]
            with AgentActivationLogger(db_conn, turn_id=turn_id, agent_name=agent_name):
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
