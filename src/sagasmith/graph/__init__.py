"""LangGraph orchestration, routing, and thin graph nodes.

The graph package is split across state, routing, graph construction, and
bootstrap modules. Later plans (04-02, 04-03) add checkpointing, interrupts,
and activation logging.
"""

from sagasmith.graph.activation_log import (
    AgentActivation,
    AgentActivationLogger,
    get_current_activation,
)
from sagasmith.graph.bootstrap import AgentServices, GraphBootstrap, build_default_graph
from sagasmith.graph.checkpoints import (
    CheckpointKind,
    build_checkpointer,
    extract_checkpoint_id,
)
from sagasmith.graph.graph import build_saga_graph
from sagasmith.graph.routing import PHASE_TO_ENTRY, route_by_phase
from sagasmith.graph.runtime import GraphRuntime, build_persistent_graph, thread_config_for
from sagasmith.graph.state import SagaGraphState, from_saga_state, to_saga_state

__all__ = [
    "PHASE_TO_ENTRY",
    "AgentActivation",
    "AgentActivationLogger",
    "AgentServices",
    "CheckpointKind",
    "GraphBootstrap",
    "GraphRuntime",
    "SagaGraphState",
    "build_checkpointer",
    "build_default_graph",
    "build_persistent_graph",
    "build_saga_graph",
    "extract_checkpoint_id",
    "from_saga_state",
    "get_current_activation",
    "route_by_phase",
    "thread_config_for",
    "to_saga_state",
]
