"""SOLVE/ASSERT node executor (deterministic computation)."""

from typing import Dict
from .base import NodeExecutor
from ..expr import evaluate, evaluate_condition


class SolveExecutor(NodeExecutor):
    """ASSERT routes to `pass`/`fail` by evaluating `config.condition` over the in_* values.

    SOLVE runs `config.procedure_ref` (an SPL.py workflow) when given, else evaluates `config.expression` with
    the same safe evaluator; the value goes on its first out_* port. A SOLVE with neither (kernel-backed
    SymPy/Sage/Lean work) is not implemented yet and yields True."""

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        config = node_data.get('config', {})
        node_id = node_data['id']

        if node_data['type'] == "ASSERT":
            condition = config.get('condition')
            if not condition:
                raise ValueError(f"ASSERT node {node_id!r} has no config.condition")
            try:
                ok = evaluate_condition(condition, in_data)
            except ValueError as e:
                raise ValueError(f"ASSERT node {node_id!r}: {e}") from None
            return {"_route": "pass" if ok else "fail"}

        if 'procedure_ref' in config:
            from ..procedures import run_node_procedure
            return run_node_procedure(node_data, in_data, resolver, llm)

        if 'expression' in config:
            try:
                result = evaluate(config['expression'], in_data)
            except ValueError as e:
                raise ValueError(f"SOLVE node {node_id!r}: {e}") from None
        else:
            result = True              # kernel-backed SOLVE is not implemented yet
        output_ports = [p for p in node_data['ports'] if p.startswith('out_')]
        return {output_ports[0]: result} if output_ports else {}
