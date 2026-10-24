"""Policy composer - merge multiple policy sets with conflict resolution."""

from typing import List, Dict, Set
from dataclasses import dataclass
from .ast_nodes import Policy, PolicySet, Effect, Annotation


@dataclass
class CompositionRule:
    """Rule for composing policies."""
    policy_set_name: str
    priority: int  # Higher priority wins in conflicts
    scope_filter: Dict = None  # Only include policies matching this scope


class PolicyComposer:
    """Composes multiple policy sets into a unified policy set."""
    
    def __init__(self):
        self.composition_rules: List[CompositionRule] = []
    
    def add_policy_set(self, name: str, policy_set: PolicySet, priority: int = 0, scope_filter: Dict = None):
        """Add a policy set to the composition."""
        self.composition_rules.append(CompositionRule(
            policy_set_name=name,
            priority=priority,
            scope_filter=scope_filter,
        ))
        # Store the policy set
        if not hasattr(self, '_policy_sets'):
            self._policy_sets = {}
        self._policy_sets[name] = policy_set
    
    def compose(self) -> PolicySet:
        """Compose all policy sets into a single policy set."""
        composed_policies: List[Policy] = []
        seen_ids: Set[str] = set()
        
        # Sort by priority (highest first)
        sorted_rules = sorted(self.composition_rules, key=lambda r: r.priority, reverse=True)
        
        for rule in sorted_rules:
            policy_set = self._policy_sets.get(rule.policy_set_name)
            if not policy_set:
                continue
            
            for policy in policy_set.policies:
                # Apply scope filter if specified
                if rule.scope_filter and not self._matches_scope(policy, rule.scope_filter):
                    continue
                
                # Check for ID conflicts
                policy_id = self._get_policy_id(policy)
                if policy_id:
                    if policy_id in seen_ids:
                        # Conflict: higher priority wins (already added)
                        continue
                    seen_ids.add(policy_id)
                
                # Add composition metadata
                composed_policy = self._add_composition_metadata(policy, rule.policy_set_name)
                composed_policies.append(composed_policy)
        
        return PolicySet(policies=composed_policies)
    
    def _matches_scope(self, policy: Policy, scope_filter: Dict) -> bool:
        """Check if a policy matches the scope filter."""
        if not policy.scope:
            return False
        
        # Check principal
        if 'principal' in scope_filter:
            if policy.scope.principal.op == "_":
                return False
            if policy.scope.principal.entity:
                principal_str = f'{policy.scope.principal.entity.entity_type}::"{policy.scope.principal.entity.entity_id}"'
                if principal_str != scope_filter['principal']:
                    return False
        
        # Check action
        if 'action' in scope_filter:
            if policy.scope.action.op == "_":
                return False
            if policy.scope.action.entities:
                action_strs = [f'Action::"{e.entity_id}"' for e in policy.scope.action.entities]
                if scope_filter['action'] not in action_strs:
                    return False
        
        # Check resource
        if 'resource' in scope_filter:
            if policy.scope.resource.op == "_":
                return False
            if policy.scope.resource.entity:
                resource_str = f'{policy.scope.resource.entity.entity_type}::"{policy.scope.resource.entity.entity_id}"'
                if resource_str != scope_filter['resource']:
                    return False
        
        return True
    
    def _get_policy_id(self, policy: Policy) -> str:
        """Extract policy ID from annotations."""
        for ann in policy.annotations:
            if ann.name == "id":
                return ann.value
        return None
    
    def _add_composition_metadata(self, policy: Policy, source_name: str) -> Policy:
        """Add metadata about the policy's source."""
        # Add a @source annotation
        new_annotations = list(policy.annotations)
        new_annotations.append(Annotation(name="source", value=source_name))
        
        return Policy(
            effect=policy.effect,
            annotations=new_annotations,
            scope=policy.scope,
            conditions=policy.conditions,
            line=policy.line,
            column=policy.column,
        )
    
    def detect_conflicts(self) -> List[Dict]:
        """Detect conflicting policies across policy sets."""
        conflicts = []
        
        # Group policies by (principal, action, resource, condition_signature)
        policy_groups: Dict[str, List[Policy]] = {}
        
        for rule in self.composition_rules:
            policy_set = self._policy_sets.get(rule.policy_set_name)
            if not policy_set:
                continue
            
            for policy in policy_set.policies:
                signature = self._get_policy_signature(policy)
                if signature not in policy_groups:
                    policy_groups[signature] = []
                policy_groups[signature].append((rule.policy_set_name, policy))
        
        # Find conflicts (same signature, different effects)
        for signature, policies in policy_groups.items():
            if len(policies) > 1:
                effects = set(p.effect for _, p in policies)
                if len(effects) > 1:
                    # Conflict detected
                    conflicts.append({
                        'signature': signature,
                        'policies': [
                            {
                                'source': source,
                                'effect': p.effect.value,
                                'id': self._get_policy_id(p),
                            }
                            for source, p in policies
                        ],
                        'resolution': 'highest_priority_wins',
                    })
        
        return conflicts
    
    def _get_policy_signature(self, policy: Policy) -> str:
        """Generate a signature for a policy based on its scope and conditions."""
        parts = []
        
        if policy.scope:
            if policy.scope.principal.entity:
                parts.append(f"p:{policy.scope.principal.entity.entity_type}::{policy.scope.principal.entity.entity_id}")
            if policy.scope.action.entities:
                actions = ",".join([e.entity_id for e in policy.scope.action.entities])
                parts.append(f"a:{actions}")
            if policy.scope.resource.entity:
                parts.append(f"r:{policy.scope.resource.entity.entity_type}::{policy.scope.resource.entity.entity_id}")
        
        # Add condition signature (simplified)
        for condition in policy.conditions:
            parts.append(f"c:{condition.kind}")
        
        return "|".join(parts)
