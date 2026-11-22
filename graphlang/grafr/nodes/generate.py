"""GENERATE node executor (probabilistic LLM calls)."""

import json
import re
import time
from typing import Dict
from .base import NodeExecutor
from ..adapters import resolve_call
from ...logging_config import DEBUG, get_logger, log_event

_log = get_logger("grafr.nodes.generate")
PREVIEW_CHARS = 200


def prompt_text(value) -> str:
    """A value as it reads inside a prompt: text as is, a list of texts (a LOOP's `collect`) one after another with a blank line
    between, any other list or mapping as JSON; not Python's repr, which shows a chapter's line breaks as `\\n`."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return "\n\n".join(value)
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill_prompt(prompt: str, in_data: Dict) -> str:
    """Replace each `{{in_x}}` by the value on port in_x, in one pass: a value that itself contains `{{in_y}}` (a document
    about prompts, code with a template) is put in as it is, never expanded again. A placeholder with no such port stays."""
    def value(m):
        key = m.group(1)
        return prompt_text(in_data[key]) if key in in_data else m.group(0)    # a LOOP's carried value is None before the first iteration
    return _PLACEHOLDER.sub(value, prompt)


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

        prompt = fill_prompt(prompt, in_data)

        schema = config.get('phases', {}).get('post', {}).get('out_schema')
        if schema is not None:
            prompt += f"\n\nReply with JSON only (no prose), matching this JSON Schema:\n{json.dumps(schema)}"
        if in_data.get('_validation_error'):
            prompt += f"\n\nYour previous reply was rejected: {in_data['_validation_error']}\nReply again, corrected."

        if 'model' in config:
            raise ValueError(f"GENERATE node {node_data['id']!r}: config.model is now config.llm (adapter[:model], as --llm), e.g. llm: \"claude_cli:{config['model']}\"")
        adapter, model = resolve_call(llm.name, config.get('llm'), getattr(llm, 'model_override', None), getattr(llm, 'default_model', None))
        extra = {'adapter': adapter} if adapter != llm.name else {}      # a node that names another adapter than the run's
        started = time.perf_counter()
        if config.get('max_tokens') is not None:                         # the node's own output budget
            extra['max_tokens'] = int(config['max_tokens'])
        response = llm.generate(prompt, model=model, temperature=config.get('temperature'), **extra)
        log_event(_log, "llm.call", node=node_data['id'], adapter=adapter, model=model,
                  prompt_chars=len(prompt), response_chars=len(str(response)),
                  ms=round((time.perf_counter() - started) * 1000))
        log_event(_log, "llm.text", level=DEBUG, node=node_data['id'], prompt=prompt[:PREVIEW_CHARS],
                  response=str(response)[:PREVIEW_CHARS])

        output_ports = [p for p in node_data['ports'] if p.startswith('out_')]
        return {output_ports[0]: response} if output_ports else {}
