"""EVALUATE node executor (conditional routing)."""

from typing import Dict
from .base import NodeExecutor
from ..expr import evaluate_condition


class EvaluateExecutor(NodeExecutor):
    """Routes to `pass` or `fail` by evaluating `config.condition` over the node's in_* values
    (written @in_name). The evaluator is safe: see grafr/expr.py for what an expression may contain."""

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        condition = node_data.get('config', {}).get('condition')
        if not condition:
            raise ValueError(f"EVALUATE node {node_data['id']!r} has no config.condition")
        try:
            ok = evaluate_condition(condition, in_data)
        except ValueError as e:
            raise ValueError(f"EVALUATE node {node_data['id']!r}: {e}") from None
        return {"_route": "pass" if ok else "fail"}
