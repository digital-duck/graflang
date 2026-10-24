"""GENERATE node executor (probabilistic LLM calls)."""

from typing import Dict
from .base import NodeExecutor
from ..adapters import resolve_model


class GenerateExecutor(NodeExecutor):
    """Executes GENERATE nodes: builds the prompt and asks the run's LLM (`mock`, `claude_cli`, ...)."""

    def execute(self, node_data: Dict, in_data: Dict, context: Dict, resolver, llm) -> Dict:
        config = node_data.get('config', {})

        if 'prompt_ref' in config:
            prompt = resolver.resolve(config['prompt_ref'], 'prompts')['content']
        elif 'prompt_inline' in config:
            prompt = config['prompt_inline']
        elif 'procedure_ref' in config:
            from ..procedures import run_node_procedure
            return run_node_procedure(node_data, in_data, resolver, llm)
        else:
            raise ValueError(f"GENERATE node {node_data['id']!r} needs prompt_ref, prompt_inline or procedure_ref")

        for key, value in in_data.items():                 # {{in_topic}} <- the value on port in_topic
            prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        model = resolve_model(llm.name, config.get('model'), getattr(llm, 'model_override', None))
        response = llm.generate(prompt, model=model, temperature=config.get('temperature'))

        output_ports = [p for p in node_data['ports'] if p.startswith('out_')]
        return {output_ports[0]: response} if output_ports else {}
