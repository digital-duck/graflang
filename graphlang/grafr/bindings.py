"""Bindings (design E6, DODA): the graph says what to do, a bindings file says which model, which files and how much.

    # prod.bind.yaml
    llm: claude_cli:claude-sonnet-5-5       # adapter[:model], like --llm
    models: {fast: claude-haiku-5-5}        # what `model: $fast` in a node means
    params: {topic: tides}                  # default workflow parameters; --param wins
    resources:                              # replaces named resources; paths are relative to this file
      prompts: {draft: ./prod/draft.md}
    limits: {max_steps: 200, wall_time_s: 300}

`graf run flow.graph.yaml --bind prod.bind.yaml`. A flag on the command line beats the bindings file, which beats the
graph's own `model:` hints. A `model: $name` with no binding falls back to the run's default model.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML

KEYS = {"llm", "models", "params", "resources", "limits"}
LIMITS = {"max_steps", "wall_time_s"}
KINDS = ("prompts", "procedures", "policies")


def load_bindings(path: Path) -> Dict[str, Any]:
    path = Path(path)
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: a bindings file is a mapping (llm, models, params, resources, limits)")
    unknown = sorted(set(data) - KEYS)
    if unknown:
        raise ValueError(f"{path.name}: unknown key(s) {unknown} (use {sorted(KEYS)})")
    limits = data.get("limits") or {}
    if "max_cost" in limits:
        raise ValueError(f"{path.name}: limits.max_cost is not supported (adapters do not report cost); use max_steps or wall_time_s")
    bad = sorted(set(limits) - LIMITS)
    if bad:
        raise ValueError(f"{path.name}: unknown limit(s) {bad} (use {sorted(LIMITS)})")
    for key in ("max_steps", "wall_time_s"):
        if key in limits and not (isinstance(limits[key], (int, float)) and not isinstance(limits[key], bool) and limits[key] > 0):
            raise ValueError(f"{path.name}: limits.{key} must be a number > 0")
    for kind, names in (data.get("resources") or {}).items():
        if kind not in KINDS or not isinstance(names, dict):
            raise ValueError(f"{path.name}: resources.{kind} must be a mapping under one of {KINDS}")
    for key in ("models", "params"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"{path.name}: {key} must be a mapping")
    out = dict(data)
    out["resources"] = {kind: {name: str((path.resolve().parent / rel)) for name, rel in names.items()}
                        for kind, names in (data.get("resources") or {}).items()}
    return out


def _walk(nodes: List[Dict], models: Dict[str, str], warnings: List[str]) -> None:
    for n in nodes:
        cfg = n.get("config", {})
        model = cfg.get("model")
        if isinstance(model, str) and model.startswith("$"):
            if model[1:] in models:
                cfg["model"] = models[model[1:]]
            else:
                del cfg["model"]
                warnings.append(f"node {n['id']!r}: model {model} has no binding; the run's default model is used")
        body = cfg.get("subgraph")
        if isinstance(body, dict):
            _walk(body.get("nodes", []), models, warnings)


def bind_graph(graph_data: Dict, bindings: Dict[str, Any]) -> Tuple[Dict, List[str]]:
    """A copy of the graph with the bindings applied, and warnings (unbound `$model`s, resources the graph does not name)."""
    graph = copy.deepcopy(graph_data)
    warnings: List[str] = []
    _walk(graph["nodes"], bindings.get("models") or {}, warnings)
    resources = graph.setdefault("resources", {})
    for kind, names in (bindings.get("resources") or {}).items():
        for name, path in names.items():
            if name not in (resources.get(kind) or {}):
                warnings.append(f"bindings: the graph has no {kind[:-1]} {name!r} to replace")
            resources.setdefault(kind, {})[name] = path
    return graph, warnings
