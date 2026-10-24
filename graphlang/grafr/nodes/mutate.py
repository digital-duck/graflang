"""MUTATE nodes are executed by the runtime itself (GraphLangRuntime._run_mutate): applying a delta
needs the live graph. This class only keeps the node type registered."""

from typing import Dict
from .base import NodeExecutor


class MutateExecutor(NodeExecutor):
    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        raise RuntimeError("MUTATE is executed by GraphLangRuntime, not through the executor registry")
