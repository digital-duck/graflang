"""Which kind of graph YAML is this? GraphLang workflows and the graph.yaml of zinet, ConceptBook and graph-code are all YAML
files that persist a graph, and any of them may be named `graph.yaml`, so the file name never decides: the top-level keys do.

  GraphLang workflow   `workflow:` + `nodes:` + `edges:`  (typed nodes with ports; may contain cycles; `graf run|vis|compile`)
  zinet graph          `primitives:` / `concepts:` / `applications:` as lists of nodes with `deps`  (the `zinet` tool)
  ConceptBook graph    the same three layers as mappings keyed by id, with `composed_of` / `needs`  (ConceptBook, graph-code)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

GRAPHLANG, ZINET, CONCEPTBOOK, UNKNOWN = "graphlang", "zinet", "conceptbook", "unknown"
ZINET_LAYERS = ("primitives", "concepts", "applications")


def detect(data: Any) -> str:
    """'graphlang', 'zinet', 'conceptbook' or 'unknown' for an already-parsed YAML document."""
    if not isinstance(data, dict):
        return UNKNOWN
    if "workflow" in data or ("nodes" in data and "edges" in data):
        return GRAPHLANG
    layers = [data[k] for k in ZINET_LAYERS if k in data]
    if layers:
        return CONCEPTBOOK if any(isinstance(v, dict) for v in layers) else ZINET
    return UNKNOWN


def require_graphlang(data: Any, path: str | Path) -> None:
    """Raise a ValueError that says what the file is, instead of a schema error about a missing `workflow`."""
    kind = detect(data)
    if kind in (ZINET, CONCEPTBOOK):
        layers = ", ".join(k for k in ZINET_LAYERS if k in data)
        what = "a zinet graph" if kind == ZINET else "a ConceptBook / graph-code graph (the layers are mappings with composed_of)"
        use = ("Check or draw it with `zinet validate FILE` / `zinet render FILE`." if kind == ZINET else
               "Check it with `grafcode validate FILE` (graph-code) or the ConceptBook tools; zinet reads the list form only so far.")
        raise ValueError(f"{Path(path).name} is {what} (it has {layers}), not a GraphLang workflow (workflow:, nodes:, edges:). {use}")
