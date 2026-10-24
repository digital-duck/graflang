"""Draw a workflow graph (see `model.build`) with zinet's drawing engines.

`graf vis --engine NAME`: cytoscape (interactive HTML, offline, default), graphviz (svg/png/pdf through `dot`), mermaid
(flowchart text), ascii (a text outline), and, with their extras installed, pyvis and graphify. The engines live in
`zinet.vis`; this module only says how a GraphLang workflow looks: node colour by node type, control edges (`triggers`)
solid, data edges (`binds`) dashed with the port as the label, and a LOOP drawn as a box around its body. On the interactive
page the data edges start hidden (they show for the node you hover or select) and a LOOP starts as one box.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import networkx as nx
from zinet import vis
from zinet.vis import DEFAULT_ENGINE, ENGINES, graphify_ready, pyvis_ready

from .model import TYPE_COLORS, build

_ROUND = {"INPUT", "OUTPUT", "EMIT"}
_DIAMOND = {"EVALUATE", "ASSERT", "GUARD"}
_HEXAGON = {"FORK", "JOIN"}

__all__ = ["DEFAULT_ENGINE", "ENGINES", "cytoscape_html", "graphify_ready", "graphlang_style", "hint", "pyvis_ready",
           "render", "to_dot", "to_mermaid_text"]


def _shape(kind: str) -> str:
    return "round-rectangle" if kind in _ROUND else "diamond" if kind in _DIAMOND else "hexagon" if kind in _HEXAGON else "rectangle"


def graphlang_style(title: str = "workflow") -> vis.Style:
    """How the nodes and edges built by `model.build` are drawn."""
    return vis.Style(
        label=lambda n, d: d["label"], kind=lambda n, d: d["kind"], color=lambda n, d: d["color"],
        shape=lambda n, d: _shape(d["kind"]), group=lambda n, d: d.get("parent"), info=lambda n, d: d["info"],
        edge_label=lambda u, v, d: d["label"], edge_kind=lambda u, v, d: d["relation"],
        edge_dashed=lambda u, v, d: d["relation"] == "binds", edge_info=lambda u, v, d: f"{d['sport']} → {d['tport']}",
        edge_legend=(("control", False), ("data", True)), title=title, kind_colors=dict(TYPE_COLORS),
        secondary_hidden=True, groups_collapsed=True,
        show_kind=False)                       # the colour and the legend already say the type       # first view: the control flow, loops as one box


def _title(G: nx.MultiDiGraph) -> str:
    return f'{G.graph.get("name", "workflow")} (GraphLang)'


def to_mermaid_text(G: nx.MultiDiGraph) -> str:
    return vis.to_mermaid_text(G, graphlang_style())


def to_dot(G: nx.MultiDiGraph, fixed_size: bool = False) -> str:
    return vis.to_dot(G, graphlang_style(), fixed_size)


def cytoscape_html(G: nx.MultiDiGraph, note: str = "") -> str:
    return vis.cytoscape_html(G, graphlang_style(_title(G)), note)


def hint(text: str) -> str:
    """zinet's install hints name zinet's extras; GraphLang users install them through GraphLang's."""
    return text.replace("zinet[pyvis]", "graflang[vis]").replace("zinet[graphify]", "graflang[graphify]")


def render(graph_data: Dict[str, Any], out: str | Path, engine: str = DEFAULT_ENGINE) -> Tuple[Path, str, int]:
    """Draw the workflow with `engine` into `out`. Returns (file, note, node count)."""
    G, note = build(graph_data)
    if not G.number_of_nodes():
        raise ValueError("nothing to draw: the workflow has no nodes")
    try:
        path = vis.render(G, out, engine, graphlang_style(_title(G)), note)
    except RuntimeError as e:
        raise RuntimeError(hint(str(e))) from None
    return path, note, G.number_of_nodes()
