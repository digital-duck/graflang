"""Base node executor."""

from typing import Dict, Any

class NodeExecutor:
    """Base executor for GraphLang nodes."""
    
    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        """Execute a node. Returns a dict of output variables."""
        # Default implementation: pass-through
        return {}
