"""CONTEXT node executor (persistent state)."""

from typing import Dict, Any
from .base import NodeExecutor

class ContextExecutor(NodeExecutor):
    """Executes CONTEXT nodes (persistent state management)."""
    
    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        config = node_data.get('config', {})
        action = config.get('action', 'read')
        target_key = config.get('target_key', 'global_state')
        
        if action == 'append':
            # Append data to context
            base = in_data.get('in_base', '')
            appendage = in_data.get('in_appendage', '')
            merged = f"{base}\n\n{appendage}"
            context[target_key] = merged
            return {"out_merged": merged}
        
        elif action == 'set':
            # a lifted `@x := expr`: the expression over the in_* values, put on the node's one out_* port
            from ..expr import evaluate
            try:
                value = evaluate(config['expression'], in_data)
            except (KeyError, ValueError) as e:
                raise ValueError(f"CONTEXT node {node_data['id']!r}: {e}") from None
            outs = [p for p in node_data['ports'] if p.startswith('out_')]
            return {outs[0]: value} if outs else {}

        elif action == 'read':
            # Read from context
            return {"out_data": context.get(target_key)}
        
        return {}
