"""Policy visualization - generate Mermaid diagrams showing policy coverage."""

from typing import Dict, List, Set
from pathlib import Path
from ruamel.yaml import YAML

from .cedar.lexer import CedarLexer
from .cedar.parser import CedarParser
from .cedar.slicer import PolicySlicer, GuardNodeConfig
from .cedar.composer import PolicyComposer


class PolicyVisualizer:
    """Generates Mermaid diagrams showing policy coverage across GUARD nodes."""
    
    def __init__(self, graph_data: Dict, resources: Dict):
        self.graph_data = graph_data
        self.resources = resources
        self.guard_nodes = self._find_guard_nodes()
        self.policy_sets = self._load_policy_sets()
    
    def _find_guard_nodes(self) -> List[Dict]:
        """Find all GUARD nodes in the graph."""
        return [n for n in self.graph_data['nodes'] if n['type'] == 'GUARD']
    
    def _load_policy_sets(self) -> Dict[str, any]:
        """Load and parse all policy sets."""
        policy_sets = {}
        
        if 'policies' in self.resources:
            for name, data in self.resources['policies'].items():
                lexer = CedarLexer(data['content'])
                tokens = lexer.tokenize()
                parser = CedarParser(tokens)
                policy_sets[name] = parser.parse()
        
        return policy_sets
    
    def generate_mermaid(self, output_path: Path = None) -> str:
        """Generate a Mermaid diagram showing policy coverage."""
        lines = [
            "graph TD",
            "    %% GUARD Nodes",
        ]
        
        # Add GUARD nodes
        for guard in self.guard_nodes:
            node_id = guard['id']
            config = guard.get('config', {})
            policy_refs = config.get('policy_refs', [config.get('policy_ref', 'unknown')])
            
            lines.append(f'    {node_id}["{node_id}<br/>GUARD"]')
            lines.append(f'    style {node_id} fill:#ff6b6b,stroke:#c92a2a,stroke-width:3px')
        
        lines.append("")
        lines.append("    %% Policies")
        
        # Add policy nodes and connections
        policy_nodes = set()
        for guard in self.guard_nodes:
            node_id = guard['id']
            config = guard.get('config', {})
            guard_config = GuardNodeConfig(node_id, config)
            
            # Get applicable policies
            applicable_policies = self._get_applicable_policies(guard_config)
            
            for policy_name, policies in applicable_policies.items():
                for policy in policies:
                    policy_id = self._get_policy_id(policy)
                    if not policy_id:
                        policy_id = f"{policy_name}_{id(policy)}"
                    
                    if policy_id not in policy_nodes:
                        policy_nodes.add(policy_id)
                        effect_color = "#51cf66" if policy.effect.value == "permit" else "#ff6b6b"
                        effect_symbol = "✓" if policy.effect.value == "permit" else "✗"
                        
                        lines.append(f'    {policy_id}["{effect_symbol} {policy_id}<br/>{policy.effect.value}"]')
                        lines.append(f'    style {policy_id} fill:{effect_color},stroke:#2b8a3e,stroke-width:2px')
                    
                    # Connect GUARD to policy
                    lines.append(f'    {node_id} --> {policy_id}')
        
        lines.append("")
        lines.append("    %% Legend")
        lines.append('    subgraph Legend')
        lines.append('        direction LR')
        lines.append('        permit["✓ permit"]')
        lines.append('        forbid["✗ forbid"]')
        lines.append('        guard["GUARD node"]')
        lines.append('    end')
        lines.append('    style permit fill:#51cf66')
        lines.append('    style forbid fill:#ff6b6b')
        lines.append('    style guard fill:#ff6b6b,stroke:#c92a2a,stroke-width:3px')
        
        mermaid_code = "\n".join(lines)
        
        if output_path:
            output_path.write_text(mermaid_code, encoding='utf-8')
        
        return mermaid_code
    
    def _get_applicable_policies(self, guard_config: GuardNodeConfig) -> Dict[str, List]:
        """Get all policies applicable to a GUARD node."""
        applicable = {}
        
        # Handle composition (multiple policy refs)
        if len(guard_config.policy_refs) > 1:
            composer = PolicyComposer()
            for i, policy_ref in enumerate(guard_config.policy_refs):
                policy_name = policy_ref.split('.')[-1]
                if policy_name in self.policy_sets:
                    composer.add_policy_set(
                        policy_name,
                        self.policy_sets[policy_name],
                        priority=guard_config.composition_priority + i,
                    )
            
            composed = composer.compose()
            applicable['composed'] = composed.policies
        else:
            # Single policy ref - use slicer
            policy_ref = guard_config.policy_refs[0] if guard_config.policy_refs else None
            if policy_ref:
                policy_name = policy_ref.split('.')[-1]
                if policy_name in self.policy_sets:
                    slicer = PolicySlicer(self.policy_sets[policy_name])
                    sliced = slicer.slice_for_guard(guard_config)
                    applicable[policy_name] = sliced.policies
        
        return applicable
    
    def _get_policy_id(self, policy) -> str:
        """Extract policy ID from annotations."""
        for ann in policy.annotations:
            if ann.name == "id":
                return ann.value
        return None
    
    def generate_coverage_report(self) -> Dict:
        """Generate a detailed coverage report."""
        report = {
            'total_guard_nodes': len(self.guard_nodes),
            'total_policies': sum(len(ps.policies) for ps in self.policy_sets.values()),
            'guard_details': [],
        }
        
        for guard in self.guard_nodes:
            node_id = guard['id']
            config = guard.get('config', {})
            guard_config = GuardNodeConfig(node_id, config)
            
            applicable = self._get_applicable_policies(guard_config)
            
            guard_detail = {
                'node_id': node_id,
                'policy_refs': guard_config.policy_refs,
                'applicable_policies': [],
                'forbid_count': 0,
                'permit_count': 0,
            }
            
            for policy_name, policies in applicable.items():
                for policy in policies:
                    policy_id = self._get_policy_id(policy) or f"unnamed_{id(policy)}"
                    guard_detail['applicable_policies'].append({
                        'id': policy_id,
                        'source': policy_name,
                        'effect': policy.effect.value,
                    })
                    
                    if policy.effect.value == 'forbid':
                        guard_detail['forbid_count'] += 1
                    else:
                        guard_detail['permit_count'] += 1
            
            report['guard_details'].append(guard_detail)
        
        return report
