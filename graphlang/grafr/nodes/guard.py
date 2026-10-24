"""GUARD node executor (Cedar policy checkpoint)."""

from typing import Dict
from .base import NodeExecutor
from ..cedar_guard import CedarGuard
from ..expr import evaluate
from ...logging_config import INFO, WARNING, get_logger, log_event

_log = get_logger("grafr.nodes.guard")


class GuardExecutor(NodeExecutor):
    """Routes to `allow` or `deny` according to a Cedar policy.

    config:
      policy_ref        `policies.<name>` from the graph's resources (required: a guard without a policy would
                        allow everything, so it is an error)
      principal/action/resource   Cedar entities; defaults Service::"llm-agent", Action::"mutate_graph",
                        Graph::"execution_topology"
      context_mapping   {attribute: "<expression>"}: the Cedar context. Expressions use the safe evaluator over
                        this node's in_* values (e.g. {cycle: "@in_cycle", max_cycles: "@in_max_cycles"}).
    Fail closed: any evaluation error denies.
    """

    def __init__(self):
        self.guard = CedarGuard()

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        config = node_data.get('config', {})
        node_id = node_data['id']
        policy_ref = config.get('policy_ref')
        if not policy_ref:
            raise ValueError(f"GUARD node {node_id!r} has no config.policy_ref")
        self.guard.load_policy(policy_ref, resolver.resolve(policy_ref, 'policies')['content'])
        try:
            cedar_context = {k: evaluate(expr, in_data) for k, expr in config.get('context_mapping', {}).items()}
        except ValueError as e:
            raise ValueError(f"GUARD node {node_id!r}: context_mapping: {e}") from None
        decision = self.guard.decide(
            policy_ref,
            config.get('principal', 'Service::"llm-agent"'),
            config.get('action', 'Action::"mutate_graph"'),
            config.get('resource', 'Graph::"execution_topology"'),
            cedar_context)
        log_event(_log, "guard.decision", level=INFO if decision.allowed else WARNING, node=node_id, policy=policy_ref,
                  allowed=decision.allowed, reason=decision.explain(), context=cedar_context)
        return {"_route": "allow" if decision.allowed else "deny", "_reason": decision.explain()}
