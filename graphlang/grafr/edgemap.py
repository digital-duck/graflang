"""An edge's `map:` (design: graflang-semantics.md 5a): a small pure expression written on a `binds` edge, injected into the consuming
node's `phases.pre.map` when the graph loads, so the runtime still sees the computation inside a node.

    - {source: a.out_text, target: b.in_query, type: binds, map: "strip(@in_query)"}

The expression is the one `phases.pre.map` takes: it reads the target node's in_* values (usually the port the edge feeds) and its result
replaces that port's value. Written here it reads as f on the arrow; after loading the edge is a plain bind and the node holds the map.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _scope(nodes: List[Dict], edges: List[Dict], where: str) -> None:
    by_id = {n["id"]: n for n in nodes}
    writers: Dict[str, int] = {}
    for e in edges:
        if e.get("type") == "binds":
            writers[e["target"]] = writers.get(e["target"], 0) + 1
    for e in edges:
        if "map" not in e:
            continue
        label = f"{where}edge {e['source']} -> {e['target']}"
        if e.get("type") != "binds":
            raise ValueError(f"{label}: only a binds edge carries a map")
        if not isinstance(e["map"], str) or not e["map"].strip():
            raise ValueError(f"{label}: map must be an expression such as \"strip(@in_query)\"")
        node_id, _, port = e["target"].partition(".")
        node = by_id.get(node_id)
        if node is None or port not in node.get("ports", []) or not port.startswith("in_"):
            raise ValueError(f"{label}: the target must be an in_* port of a node of this graph")
        if writers[e["target"]] > 1:
            raise ValueError(f"{label}: {e['target']} has several writers; a map belongs to a port with one (the node cannot tell which edge wrote the value)")
        mapping = node.setdefault("config", {}).setdefault("phases", {}).setdefault("pre", {}).setdefault("map", {})
        if port in mapping:
            raise ValueError(f"{label}: {node_id} already maps {port} in phases.pre.map")
        mapping[port] = e.pop("map")
    for n in nodes:
        body = (n.get("config") or {}).get("subgraph")
        if isinstance(body, dict):
            _scope(body.get("nodes", []), body.get("edges", []), f"{where}{n['id']}/")


def inject_edge_maps(graph: Dict[str, Any]) -> None:
    """Move every edge `map` of the graph (and of its loop bodies) into the target node's `phases.pre.map`. Does nothing without maps."""
    _scope(graph.get("nodes", []), graph.get("edges", []), "")
