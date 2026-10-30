"""JOIN: a barrier, and optionally the point where several values become one."""

from typing import Dict
from .base import NodeExecutor


class JoinExecutor(NodeExecutor):
    """Fires once every incoming control edge has delivered (the runtime does that). If the node has `in_*` ports it also
    bundles them: its one `out_*` port gets an object keyed by the port names without `in_`, the counterpart of Python's
    `**kwargs`. A node downstream reads a field with `@in_args.topic`. With no `in_*` ports it only waits."""

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        ports = node_data["ports"]
        ins = [p for p in ports if p.startswith("in_")]
        outs = [p for p in ports if p.startswith("out_")]
        if not ins:
            return {}
        if len(outs) != 1:
            raise ValueError(f"JOIN {node_data['id']!r} bundles its inputs onto one out_* port, found {len(outs)}")
        return {outs[0]: {p[3:]: in_data.get(p) for p in ins}}
