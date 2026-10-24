"""Which kind of graph YAML is this? GraphLang workflows and zinet graphs are both YAML files that persist a graph,
and either may be named `graph.yaml`, so the file name never decides: the top-level keys do.

  GraphLang workflow   `workflow:` + `nodes:` + `edges:`  (typed nodes with ports; may contain cycles; `graf run|vis|compile`)
  zinet graph          `primitives:` / `concepts:` / `applications:`  (a dependency DAG; the `zinet` tool)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

GRAPHLANG, ZINET, UNKNOWN = "graphlang", "zinet", "unknown"
ZINET_LAYERS = ("primitives", "concepts", "applications")


def detect(data: Any) -> str:
    """'graphlang', 'zinet' or 'unknown' for an already-parsed YAML document."""
    if not isinstance(data, dict):
        return UNKNOWN
    if "workflow" in data or ("nodes" in data and "edges" in data):
        return GRAPHLANG
    if any(k in data for k in ZINET_LAYERS):
        return ZINET
    return UNKNOWN


def require_graphlang(data: Any, path: str | Path) -> None:
    """Raise a ValueError that says what the file is, instead of a schema error about a missing `workflow`."""
    if detect(data) == ZINET:
        layers = ", ".join(k for k in ZINET_LAYERS if k in data)
        raise ValueError(
            f"{Path(path).name} is a zinet graph (it has {layers}), not a GraphLang workflow (workflow:, nodes:, edges:). "
            "Check or draw it with `zinet validate FILE` / `zinet render FILE`.")
