from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ACYCLIC_RELATION_TYPES = frozenset({"IS_A", "INSTANCE_OF"})


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_RETRY = "WAITING_RETRY"
    WAITING_INPUT = "WAITING_INPUT"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class RunOutcome(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepKind(str, Enum):
    INVENTORY = "INVENTORY"
    PLAN = "PLAN"
    SCOUT = "SCOUT"
    ACQUIRE = "ACQUIRE"
    EXTRACT = "EXTRACT"
    SYNTHESIZE = "SYNTHESIZE"
    AUDIT = "AUDIT"
    INTEGRATE = "INTEGRATE"
    SUMMARIZE = "SUMMARIZE"
    COMPLETE = "COMPLETE"


TERMINAL_STATUSES = frozenset(
    {RunStatus.CANCELLED, RunStatus.SUCCEEDED, RunStatus.FAILED}
)

LEGAL_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLING, RunStatus.CANCELLED}
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_RETRY,
            RunStatus.WAITING_INPUT,
            RunStatus.CANCELLING,
            RunStatus.CANCELLED,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.WAITING_RETRY: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLING, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.WAITING_INPUT: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLING, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.CANCELLING: frozenset({RunStatus.CANCELLED, RunStatus.FAILED}),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
}


def legal_transition(current: RunStatus, target: RunStatus) -> bool:
    return target in LEGAL_TRANSITIONS[current]


class GraphCycleError(ValueError):
    def __init__(self) -> None:
        super().__init__("taxonomy and instance inheritance cycle detected")


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    relation_type: str


def ensure_valid_graph(edges: tuple[GraphEdge, ...]) -> None:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation_type not in ACYCLIC_RELATION_TYPES:
            continue
        adjacency.setdefault(edge.source_id, set()).add(edge.target_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise GraphCycleError
        if node_id in visited:
            return
        visiting.add(node_id)
        for target_id in adjacency.get(node_id, ()):
            visit(target_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in adjacency:
        visit(node_id)
