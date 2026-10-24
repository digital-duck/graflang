"""Node executors for GraphLang."""

from .base import NodeExecutor
from .generate import GenerateExecutor
from .solve import SolveExecutor
from .evaluate import EvaluateExecutor
from .loop import LoopExecutor
from .guard import GuardExecutor
from .context import ContextExecutor
from .mutate import MutateExecutor

_EXECUTORS = {
    "INPUT": NodeExecutor(),
    "OUTPUT": NodeExecutor(),
    "GENERATE": GenerateExecutor(),
    "SOLVE": SolveExecutor(),
    "ASSERT": SolveExecutor(),  # ASSERT uses the same executor as SOLVE
    "EVALUATE": EvaluateExecutor(),
    "LOOP": LoopExecutor(),
    "GUARD": GuardExecutor(),
    "CONTEXT": ContextExecutor(),
    "MUTATE": MutateExecutor(),
    "FORK": NodeExecutor(),
    "JOIN": NodeExecutor(),
    "RECOVER": NodeExecutor(),
    "OBSERVE": NodeExecutor(),
    "EMIT": NodeExecutor(),
    "QUERY": NodeExecutor(),
}

def register_executor(node_type: str, executor: NodeExecutor) -> None:
    """Install (or replace) the executor for a node type."""
    _EXECUTORS[node_type] = executor


def get_node_executor(node_type: str) -> NodeExecutor:
    """Get the executor for a node type."""
    if node_type not in _EXECUTORS:
        raise ValueError(f"Unknown node type: {node_type}")
    return _EXECUTORS[node_type]
