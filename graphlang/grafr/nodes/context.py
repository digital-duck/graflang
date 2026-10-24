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
        
        elif action == 'read':
            # Read from context
            return {"out_data": context.get(target_key)}
        
        return {}
