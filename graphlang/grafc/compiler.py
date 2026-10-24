"""Main GraphLang compiler orchestrator."""

import json
from pathlib import Path
from typing import Dict, Any, List
from ruamel.yaml import YAML
from jsonschema import validate, ValidationError

from ..formats import require_graphlang
from .analyzer import GraphAnalyzer
from .optimizer import GraphOptimizer
from .cedar_compiler import CedarCompiler

class GraphLangCompiler:
    """Compiles GraphLang workflows to Rust."""
    
    def __init__(
        self,
        graph_path: Path,
        output_dir: Path = None,
        target: str = "rust",
        optimize: bool = False,
    ):
        self.graph_path = graph_path
        self.output_dir = output_dir or Path(f"{graph_path.stem}_compiled")
        self.target = target
        self.optimize = optimize
        
        self.graph_data: Dict = None
        self.resources: Dict = {}
        self.analysis: Dict = None
        self.optimizations: List = []
        self.compiled_policies: Dict = {}
        self.rust_code: Dict = {}
    
    def load_graph(self):
        """Load and validate the GraphLang YAML."""
        yaml = YAML()
        with open(self.graph_path, 'r') as f:
            self.graph_data = yaml.load(f)
        require_graphlang(self.graph_data, self.graph_path)
        
        # Validate against schema
        schema_path = Path(__file__).parent.parent / "schema" / "graflang-ir.json"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            try:
                validate(instance=self.graph_data, schema=schema)
            except ValidationError as e:
                raise ValueError(f"Schema validation failed: {e.message}")
        
        # Store source directory for resource resolution
        self.graph_data['_source_dir'] = str(self.graph_path.parent)
    
    def resolve_resources(self):
        """Resolve all Tier 2 resources (procedures, prompts, policies)."""
        if 'resources' not in self.graph_data:
            return
        
        base_dir = Path(self.graph_data['_source_dir'])
        
        for res_type, res_dict in self.graph_data['resources'].items():
            self.resources[res_type] = {}
            for name, path in res_dict.items():
                file_path = base_dir / path.lstrip('./')
                if not file_path.exists():
                    raise FileNotFoundError(f"Resource not found: {name} at {file_path}")
                
                content = file_path.read_text(encoding='utf-8')
                self.resources[res_type][name] = {
                    'path': str(file_path),
                    'content': content,
                }
    
    def analyze(self):
        """Analyze the graph topology."""
        analyzer = GraphAnalyzer(self.graph_data)
        self.analysis = analyzer.analyze()
    
    def optimize(self):
        """Apply graph-level optimizations."""
        optimizer = GraphOptimizer(self.graph_data, self.analysis)
        self.optimizations = optimizer.optimize()
        # Apply optimizations to graph_data
        self.graph_data = optimizer.get_optimized_graph()
    
    def compile_policies(self):
        """Compile Cedar policies to Rust."""
        if 'policies' not in self.resources:
            return
        
        cedar_compiler = CedarCompiler()
        for policy_name, policy_data in self.resources['policies'].items():
            rust_code = cedar_compiler.compile(policy_data['content'])
            self.compiled_policies[policy_name] = rust_code
    
    def generate_rust(self):
        """Generate Rust code from the Graph IR."""
        try:
            from .rust_gen.codegen import RustCodeGenerator      # needs jinja2: only `graf compile` uses it
        except ImportError as e:
            raise ValueError(f"`graf compile` needs the Rust code generator's template engine: pip install 'graflang[grafc]' ({e})") from None
        codegen = RustCodeGenerator(
            graph_data=self.graph_data,
            resources=self.resources,
            analysis=self.analysis,
            compiled_policies=self.compiled_policies,
        )
        self.rust_code = codegen.generate()
    
    def write_output(self):
        """Write the generated Rust project to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write Cargo.toml
        with open(self.output_dir / "Cargo.toml", 'w') as f:
            f.write(self.rust_code['Cargo.toml'])
        
        # Write src/ files
        src_dir = self.output_dir / "src"
        src_dir.mkdir(exist_ok=True)
        
        for filename, content in self.rust_code.items():
            if filename != "Cargo.toml":
                with open(src_dir / filename, 'w') as f:
                    f.write(content)
        
        # Copy resource files (prompts, etc.)
        resources_dir = self.output_dir / "resources"
        resources_dir.mkdir(exist_ok=True)
        
        for res_type, res_dict in self.resources.items():
            type_dir = resources_dir / res_type
            type_dir.mkdir(exist_ok=True)
            for name, data in res_dict.items():
                with open(type_dir / f"{name}.{res_type.rstrip('s')}", 'w') as f:
                    f.write(data['content'])
