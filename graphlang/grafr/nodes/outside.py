"""QUERY, EMIT and OBSERVE executors. They need the run (the graph's folder, whether effects are real, the output folder), so the
runtime calls `execute_with(runtime, node_data, in_data)`; a test that registers its own executor for the type replaces them."""
from typing import Any, Dict

from .base import NodeExecutor
from ..decision import run_decision
from ..outside import run_emit, run_observe, run_query


class QueryExecutor(NodeExecutor):
    def execute_with(self, rt, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        return run_query(node_data, in_data, rt.resolver.base_dir)


class EmitExecutor(NodeExecutor):
    def execute_with(self, rt, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        return run_emit(node_data, in_data, rt.resolver.base_dir, rt.effects)


class ObserveExecutor(NodeExecutor):
    def execute_with(self, rt, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        return run_observe(node_data, in_data, rt.node_output, rt.steps)


class DecisionExecutor(NodeExecutor):
    def execute_with(self, rt, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        return run_decision(node_data, in_data, rt.answers, rt.ask, rt.answered_by)
