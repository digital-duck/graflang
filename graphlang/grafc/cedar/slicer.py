"""Policy slicer: keep only the policies that can apply to one GUARD node's request.

A GUARD asks one fixed question (principal, action, resource). A policy can be dropped only when its scope
provably cannot match that question; every other policy stays, including the unscoped ones (`permit(principal,
action, resource) when {...}`, and above all unscoped `forbid`s). Dropping a policy that might apply would
change decisions, so the rules are conservative:

* `principal == X` / `resource == X` / `action == X` with X different from the guard's entity: dropped.
* `principal is T` (and `is T in ...`): dropped if T is not the guard entity's type.
* `in` constraints are kept: whether the guard's entity is in the group depends on the entity hierarchy,
  which is only known at run time.
* Anything with no constraint is kept.

`tests/test_cedar_differential.py` checks that the sliced and the full policy set agree on every request the
guard can make.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Set

from .ast_nodes import Policy, PolicySet, Effect

ENTITY_RE = re.compile(r'^\s*([A-Za-z_][\w:]*)::"((?:[^"\\]|\\.)*)"\s*$')


@dataclass
class GuardNodeConfig:
    """The question a GUARD node asks Cedar."""
    node_id: str
    policy_ref: Optional[str] = None
    principal: str = 'Service::"llm-agent"'
    action: str = 'Action::"mutate_graph"'
    resource: str = 'Graph::"execution_topology"'
    context_keys: Set[str] = None

    def __init__(self, node_id: str, config: Dict):
        self.node_id = node_id
        self.policy_ref = config.get('policy_ref')
        self.principal = _normalise(config.get('principal', 'Service::"llm-agent"'))
        self.action = _normalise(config.get('action', 'Action::"mutate_graph"'))
        self.resource = _normalise(config.get('resource', 'Graph::"execution_topology"'))
        self.context_keys = set(config.get('context_mapping', {}).keys())


def _normalise(text: str) -> str:
    """`Action::allow_retry` -> `Action::"allow_retry"`."""
    m = re.fullmatch(r'([A-Za-z_][\w:]*)::"?([^"]+)"?', text.strip())
    return f'{m.group(1)}::"{m.group(2)}"' if m else text


def _split(entity: str):
    m = ENTITY_RE.match(entity)
    return (m.group(1), m.group(2)) if m else (entity, "")


class PolicySlicer:
    """Slices a policy set for a GUARD node."""

    def __init__(self, policy_set: PolicySet):
        self.policy_set = policy_set

    def can_apply(self, policy: Policy, guard: GuardNodeConfig) -> bool:
        """False only if the policy's scope cannot match the guard's request."""
        s = policy.scope
        if s is None:
            return True
        for constraint, entity in ((s.principal, guard.principal), (s.resource, guard.resource)):
            ty, ident = _split(entity)
            if constraint.op == "eq" and (constraint.entity.entity_type, constraint.entity.entity_id) != (ty, ident):
                return False
            if constraint.op in ("is", "is_in") and constraint.entity_type != ty:
                return False
        if s.action.op == "eq":
            ty, ident = _split(guard.action)
            e = s.action.entities[0]
            if (e.entity_type, e.entity_id) != (ty, ident):
                return False
        return True

    def slice_for_guard(self, guard_config: GuardNodeConfig) -> PolicySet:
        kept = [p for p in self.policy_set.policies if self.can_apply(p, guard_config)]
        return PolicySet(policies=kept)

    def get_slice_stats(self, guard_config: GuardNodeConfig) -> Dict:
        sliced = self.slice_for_guard(guard_config)
        total, kept = len(self.policy_set.policies), len(sliced.policies)
        return {
            'total_policies': total,
            'sliced_policies': kept,
            'reduction_percent': ((total - kept) / total * 100) if total else 0,
            'forbid_count': sum(1 for p in sliced.policies if p.effect == Effect.FORBID),
            'permit_count': sum(1 for p in sliced.policies if p.effect == Effect.PERMIT),
        }
