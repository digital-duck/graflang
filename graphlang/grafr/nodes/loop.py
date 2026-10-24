"""LOOP nodes are executed by the runtime itself (GraphLangRuntime._run_loop), because running a
subgraph needs the runtime. This class only exists so the node type stays registered."""

from typing import Dict
from .base import NodeExecutor


class LoopExecutor(NodeExecutor):
    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        raise RuntimeError("LOOP is executed by GraphLangRuntime, not through the executor registry")
