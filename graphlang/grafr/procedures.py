"""Run an SPL.py workflow (a Tier-2 `procedure_ref`) and return its output, using SPL.py's own executor.

This mirrors what `spl3 run` does for one file: load the sibling .spl files into a registry (so IMPORT
and CALL resolve), register the file's functions/procedures/TOOL_APIs, build an Executor around the
chosen adapter, and run the workflow. Needs SPL.py importable (see adapters.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .adapters import _import_spl_get_adapter, _run_coro


def declared_inputs(path: Path) -> list[str]:
    """Names of the workflow INPUT parameters in an .spl file (the last WORKFLOW defined, as `spl3 run` picks)."""
    from spl3._loader import load_workflows_from_file
    defns = load_workflows_from_file(Path(path))
    if not defns:
        raise ValueError(f"{path} defines no WORKFLOW")
    return [p.name for p in defns[-1].ast_node.inputs]


async def _run(path: Path, params: Dict[str, str], adapter_name: str, model: Optional[str], workflow: Optional[str]) -> str:
    from types import SimpleNamespace
    from spl3._loader import load_definitions_from_file, load_workflows_from_file
    from spl3.composer import WorkflowComposer
    from spl3.executor import Executor
    from spl3.registry import LocalRegistry

    get_adapter = _import_spl_get_adapter()
    registry = LocalRegistry()
    registry.load_dir(path.parent)
    adapter = get_adapter(adapter_name, **({"model": model} if model else {}))
    executor = Executor(adapter=adapter)
    executor.composer = WorkflowComposer(registry, executor)

    tool_apis, functions, procedures = load_definitions_from_file(path)
    for stmt in functions:
        executor.functions.register(stmt)
    for stmt in procedures:
        executor.functions.register_procedure(stmt)
    executor._load_tool_apis(SimpleNamespace(statements=tool_apis))

    defns = load_workflows_from_file(path)
    if not defns:
        raise ValueError(f"{path} defines no WORKFLOW")
    stem = path.stem.replace("-", "_")
    target = (next((d for d in defns if d.name == workflow), None) if workflow
              else next((d for d in defns if d.name == stem), defns[-1]))
    if target is None:
        raise ValueError(f"workflow {workflow!r} not found in {path.name}")
    result = await executor.execute_workflow(target.ast_node, params=params)
    if result.status != "complete":
        raise RuntimeError(f"procedure {target.name} ended with status {result.status}: {result.committed_value}")
    value = result.committed_value or ""
    if not value and target.ast_node.outputs:
        value = result.output.get(target.ast_node.outputs[0].name, "")
    return value


def run_procedure(path: Path, args: Dict[str, Any], adapter_name: str, model: Optional[str] = None,
                  log_dir: Optional[Path] = None, workflow: Optional[str] = None) -> str:
    """Run the workflow in `path` with `args` (graph port values, by SPL parameter name) and return its output.

    Only the parameters the workflow declares are passed. A declared `*model*` parameter gets `model` (else the
    adapter's default is left to SPL), and a declared `log_dir` goes to `log_dir`, so a procedure's side files
    land where the caller chooses instead of under the current directory.
    """
    path = Path(path)
    names = declared_inputs(path)
    params = {k: str(v) for k, v in args.items() if k in names}
    for name in names:
        if "model" in name and name not in params and model:
            params[name] = model
        if name == "log_dir" and name not in params and log_dir is not None:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            params[name] = str(log_dir)
    return _run_coro(_run(path, params, adapter_name, model, workflow))


def run_node_procedure(node_data: Dict, in_data: Dict[str, Any], resolver, llm) -> Dict[str, Any]:
    """Execute a node's `procedure_ref` (shared by GENERATE and SOLVE nodes). The SPL parameters come from the
    node's in_* ports (`in_spec` -> `spec`), or from `config.params` ({spl_parameter: in_port}) when the names
    differ. The result goes on the node's first out_* port. Under the mock adapter nothing is run."""
    config, node_id = node_data['config'], node_data['id']
    output_ports = [p for p in node_data['ports'] if p.startswith('out_')]
    path = resolver.resolve(config['procedure_ref'], 'procedures')['path']
    if llm.name == 'mock':
        text = f"[Mock procedure {config['procedure_ref']}] " + ", ".join(f"{k}={str(v)[:40]}" for k, v in in_data.items())
        return {output_ports[0]: text} if output_ports else {}
    if not hasattr(llm, 'adapter_name'):
        raise NotImplementedError(f"node {node_id!r}: procedure_ref needs an SPL.py adapter (got {llm.name!r})")
    args = {k[3:]: v for k, v in in_data.items()}
    for spl_name, port in (config.get('params') or {}).items():
        if port not in in_data:
            raise ValueError(f"node {node_id!r}: params maps {spl_name!r} to {port!r}, which has no value")
        args[spl_name] = in_data[port]
    out = run_procedure(path, args, llm.adapter_name, getattr(llm, 'model_override', None),
                        log_dir=resolver.base_dir / '.grafr' / 'logs')
    return {output_ports[0]: out} if output_ports else {}
