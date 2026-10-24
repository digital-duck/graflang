"""Rust code generator with policy slicing."""

from typing import Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from ..cedar.compiler import CedarCompiler
from ..cedar.slicer import GuardNodeConfig


class RustCodeGenerator:
    """Generates Rust code from GraphLang IR with policy slicing."""
    
    def __init__(
        self,
        graph_data: Dict,
        resources: Dict,
        analysis: Dict,
        compiled_policies: Dict,
    ):
        self.graph_data = graph_data
        self.resources = resources
        self.analysis = analysis
        self.compiled_policies = compiled_policies
        
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
        self.cedar_compiler = CedarCompiler()
    
    def generate(self) -> Dict[str, str]:
        """Generate all Rust files."""
        files = {
            'Cargo.toml': self._generate_cargo_toml(),
            'main.rs': self._generate_main(),
            'workflow.rs': self._generate_workflow(),
            'nodes.rs': self._generate_nodes(),
            'context.rs': self._generate_context(),
        }
        
        # Generate per-GUARD-node policy modules
        guard_policies = self._generate_guard_policies()
        files.update(guard_policies)
        
        # Generate unified policies.rs that dispatches to node-specific modules
        files['policies.rs'] = self._generate_policies_dispatcher(guard_policies.keys())
        
        return files
    
    def _generate_guard_policies(self) -> Dict[str, str]:
        """Generate node-specific policy modules for each GUARD node."""
        guard_policies = {}
        
        # Find all GUARD nodes
        guard_nodes = [n for n in self.graph_data['nodes'] if n['type'] == 'GUARD']
        
        for guard_node in guard_nodes:
            node_id = guard_node['id']
            config = guard_node.get('config', {})
            
            # Build guard config
            guard_config = GuardNodeConfig(
                node_id=node_id,
                config=config,
            )
            
            # Compile sliced policies for this guard
            if 'policies' in self.resources:
                for policy_name, policy_data in self.resources['policies'].items():
                    sliced_rust = self.cedar_compiler.compile_sliced(
                        policy_data['content'],
                        guard_config
                    )
                    
                    # Write to node-specific module
                    module_name = f"policy_{node_id}.rs"
                    guard_policies[module_name] = sliced_rust
        
        return guard_policies
    
    def _generate_policies_dispatcher(self, guard_modules: list) -> str:
        """Generate policies.rs that dispatches to node-specific modules."""
        lines = [
            "// Policy dispatcher - routes to node-specific policy modules",
            "",
        ]
        
        # Import all guard modules
        for module in guard_modules:
            module_name = module.replace('.rs', '')
            lines.append(f"mod {module_name};")
        
        lines.append("")
        lines.append("use crate::context::ExecutionContext;")
        lines.append("")
        
        # Generate dispatcher function
        lines.append("/// Evaluate policies for a specific GUARD node.")
        lines.append("pub fn evaluate_for_node(node_id: &str, ctx: &ExecutionContext) -> bool {")
        lines.append("    match node_id {")
        
        for module in guard_modules:
            node_id = module.replace('policy_', '').replace('.rs', '')
            module_name = module.replace('.rs', '')
            func_name = f"evaluate_{node_id}"
            lines.append(f'        "{node_id}" => {module_name}::{func_name}(ctx),')
        
        lines.append('        _ => true,  // Unknown node, allow by default')
        lines.append("    }")
        lines.append("}")
        
        return "\n".join(lines)
    
    # ... (other methods remain the same)
    def _generate_cargo_toml(self) -> str:
        template = self.env.get_template('Cargo.toml.j2')
        return template.render(
            name=self.graph_data['workflow']['name'],
            version="0.1.0",
        )
    
    def _generate_main(self) -> str:
        template = self.env.get_template('main.rs.j2')
        return template.render(
            workflow_name=self.graph_data['workflow']['name'],
        )
    
    def _generate_workflow(self) -> str:
        template = self.env.get_template('workflow.rs.j2')
        return template.render(
            workflow=self.graph_data['workflow'],
            nodes=self.graph_data['nodes'],
            edges=self.graph_data['edges'],
        )
    
    def _generate_nodes(self) -> str:
        template = self.env.get_template('nodes.rs.j2')
        return template.render(
            nodes=self.graph_data['nodes'],
            resources=self.resources,
        )
    
    def _generate_context(self) -> str:
        return '''// Execution context
use std::collections::HashMap;

pub struct ExecutionContext {
    pub data: HashMap<String, String>,
    pub principal: Entity,
    pub action: Entity,
    pub resource: Entity,
    pub context: HashMap<String, String>,
    pub proposed_delta: Option<GraphDelta>,
    pub mutation_count: usize,
    pub max_allowed_mutations: usize,
    pub human_approval: bool,
    pub contains_pii: bool,
}

pub struct Entity {
    pub id: String,
    pub parents: Vec<String>,
}

impl Entity {
    pub fn new(id: &str) -> Self {
        Self { id: id.to_string(), parents: Vec::new() }
    }
    
    pub fn is_in(&self, parent_id: &str) -> bool {
        self.id == parent_id || self.parents.contains(&parent_id.to_string())
    }
}

pub struct GraphDelta {
    pub action: String,
    pub node_type: Option<String>,
    pub source_port: Option<String>,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self {
            data: HashMap::new(),
            principal: Entity::new("llm-agent"),
            action: Entity::new("unknown"),
            resource: Entity::new("execution_topology"),
            context: HashMap::new(),
            proposed_delta: None,
            mutation_count: 0,
            max_allowed_mutations: 10,
            human_approval: false,
            contains_pii: false,
        }
    }
    
    pub fn set(&mut self, key: &str, value: String) {
        self.data.insert(key.to_string(), value);
    }
    
    pub fn get(&self, key: &str) -> Option<&String> {
        self.data.get(key)
    }
}
'''
