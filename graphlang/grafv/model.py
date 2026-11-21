"""A GraphLang workflow as a drawable `networkx.MultiDiGraph`.

Nodes are workflow nodes (kind = node type). A LOOP's sub-graph nodes get the id `<loop>/<node>` and `parent=<loop>`,
so engines can draw the loop as a box around its body. Edges carry `relation` = `triggers` (control) or `binds` (data),
plus the source and target port names.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import networkx as nx

# Node-type colours, grouped by role (flow ends, generation, decisions, structure, effects, data access).
TYPE_COLORS = {
    "INPUT": "#8a8f98", "OUTPUT": "#8a8f98", "EMIT": "#8a8f98",
    "GENERATE": "#4f8ef7",
    "EVALUATE": "#e0a21e", "ASSERT": "#e0a21e",
    "LOOP": "#9b59b6", "BATCH": "#9b59b6", "FORK": "#9b59b6", "JOIN": "#9b59b6",
    "GUARD": "#e5484d", "MUTATE": "#e5484d", "RECOVER": "#e5484d", "DECISION": "#d6409f",
    "SOLVE": "#2fa84f", "QUERY": "#2fa84f", "RUN_CODE": "#2fa84f", "CONTEXT": "#2fa84f", "OBSERVE": "#2fa84f",
}
OTHER_COLOR = "#8a8f98"
CONFIG_KEYS = ("prompt_ref", "procedure_ref", "condition", "llm", "policy_ref", "policy_refs", "expression", "temperature")


def color(node_type: str) -> str:
    return TYPE_COLORS.get(node_type, OTHER_COLOR)


LABEL_CHARS = 36
PROMPT_PREVIEW = 60                  # characters of a node's prompt_inline shown in its detail pane (the first line only)


def _short(text: str, limit: int = LABEL_CHARS) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _ref_name(ref: str) -> str:
    return str(ref).rsplit(".", 1)[-1]


def display_label(node: Dict[str, Any]) -> str:
    """What a node is called in a picture. Underscores become spaces (`write_file` is shown as `write file`); an explicit
    `config.label` is shown exactly as written. See `_summary` for how the rest is derived."""
    cfg = node.get("config") or {}
    if cfg.get("label"):
        return _short(cfg["label"])
    return _short(_summary(node).replace("_", " "))


def _summary(node: Dict[str, Any]) -> str:
    """A short summary of what a node does (the function or prompt it runs, the tool it calls, the condition it tests),
    else its id. The id stays in the side panel."""
    cfg = node.get("config") or {}
    kind = node["type"]
    if kind == "GENERATE":
        name = cfg.get("function") or (_ref_name(cfg["prompt_ref"]) if cfg.get("prompt_ref") else None)
        if name:
            return name
    if kind in ("SOLVE", "QUERY", "RECOVER", "OBSERVE", "EMIT"):
        name = cfg.get("tool") or (_ref_name(cfg["procedure_ref"]) if cfg.get("procedure_ref") else None)
        if name:
            return name
    if kind == "CONTEXT" and cfg.get("action"):
        out = next((p[4:] for p in node.get("ports", []) if p.startswith("out_")), "")
        return f"{cfg['action']} {out}".strip()
    if kind in ("EVALUATE", "ASSERT") and cfg.get("condition"):
        return str(cfg["condition"]).replace("@in_", "@").replace("@", "")
    if kind == "BATCH":
        return "for each " + cfg.get("item_var", "item")
    if kind == "LOOP" and cfg.get("condition"):
        return "repeat while " + str(cfg["condition"]).replace("@in_", "@").replace("@", "")
    return node["id"]


def _info(node: Dict[str, Any]) -> str:
    cfg = node.get("config") or {}
    lines = [f"id: {node['id']}", f"type: {node['type']}"]
    lines += [f"{k}: {cfg[k]}" for k in CONFIG_KEYS if cfg.get(k) not in (None, "", [])]
    if cfg.get("prompt_inline"):
        text = str(cfg["prompt_inline"]).strip()
        first = text.splitlines()[0]
        lines.append("prompt_inline: " + first[:PROMPT_PREVIEW] + ("..." if len(first) > PROMPT_PREVIEW or text != first else ""))     # "..." marks a cut
    lines.append("ports: " + ", ".join(node.get("ports", [])))
    return "\n".join(lines)


def _edge_label(etype: str, sport: str, tport: str) -> str:
    if etype == "binds":
        return sport[4:] if sport.startswith("out_") else sport
    return "" if sport in ("complete", "entry") else sport


def _add(G: nx.MultiDiGraph, nodes: List[Dict], edges: List[Dict], prefix: str, parent: str | None,
         notes: List[str], part_of: Dict[str, Tuple[str, str]] | None = None) -> None:
    ids = {}
    part_of = part_of or {}
    for use, pname in dict.fromkeys(tuple(part_of[n["id"]]) for n in nodes if n["id"] in part_of):    # a used part is drawn as a box
        G.add_node(prefix + use, label=f"{use} ({pname})", kind="SUBGRAPH", color=color("SUBGRAPH"), info=f"part {pname}",
                   **({"parent": parent} if parent else {}))
    for n in nodes:
        qid = prefix + n["id"]
        ids[n["id"]] = qid
        box = prefix + part_of[n["id"]][0] if n["id"] in part_of else parent
        G.add_node(qid, label=display_label(n), kind=n["type"], color=color(n["type"]), info=_info(n),
                   **({"parent": box} if box else {}))
    for e in edges:
        try:
            (s, sp), (t, tp) = (e["source"].split(".", 1), e["target"].split(".", 1))
        except ValueError:
            notes.append(f"skipped malformed edge {e.get('source')!r} -> {e.get('target')!r}")
            continue
        if s not in ids or t not in ids:
            notes.append(f"skipped edge {e['source']} -> {e['target']}: not a node of this (sub)graph")
            continue
        etype = e.get("type", "triggers")
        G.add_edge(ids[s], ids[t], relation=etype, sport=sp, tport=tp, label=_edge_label(etype, sp, tp))
    for n in nodes:                                    # a LOOP's body, recursively
        sub = (n.get("config") or {}).get("subgraph")
        if sub:
            qid = ids[n["id"]]
            _add(G, sub.get("nodes", []), sub.get("edges", []), qid + "/", qid, notes)


def _level(G: nx.MultiDiGraph, node: str) -> int:
    """How many boxes (composites, LOOP bodies) enclose the node: 0 at the top level."""
    n = 0
    while (node := G.nodes[node].get("parent")) is not None:
        n += 1
    return n


def collapse(G: nx.MultiDiGraph, depth: int) -> None:
    """Show `depth` levels: every box with `depth` or more boxes around it becomes a single node (its body hidden, its links kept).
    `depth=0` draws the top level only, each composite as one node; `depth=1` opens those and closes the ones inside them."""
    boxes = sorted({d["parent"] for _, d in G.nodes(data=True) if d.get("parent")}, key=lambda b: _level(G, b))
    for box in boxes:
        if box not in G or _level(G, box) < depth:
            continue
        inside = [n for n in G.nodes if n != box and _is_inside(G, n, box)]
        if not inside:
            continue
        links = []
        for u, v, d in G.edges(data=True):
            if (u in inside) != (v in inside):                     # a link across the box's edge now ends at the box
                a, b = (box if u in inside else u), (box if v in inside else v)
                if a != b:
                    links.append((a, b, d["relation"]))
        G.remove_nodes_from(inside)
        for a, b, relation in dict.fromkeys(links):
            G.add_edge(a, b, relation=relation, sport="", tport="", label="")
        G.nodes[box]["label"] = f"{G.nodes[box].get('label', box)} · {len(inside)} node{'s' if len(inside) != 1 else ''}"
        G.nodes[box]["collapsed_nodes"] = len(inside)


def _is_inside(G: nx.MultiDiGraph, node: str, box: str) -> bool:
    while (node := G.nodes[node].get("parent")) is not None:
        if node == box:
            return True
    return False


def build(graph_data: Dict[str, Any], depth: "int | None" = None) -> Tuple[nx.MultiDiGraph, str]:
    """The workflow as a graph, and a one-line note on anything that could not be drawn. `depth` limits how many levels of composites and
    loop bodies are opened (None: all)."""
    G = nx.MultiDiGraph(name=graph_data.get("workflow", {}).get("name", "workflow"))
    notes: List[str] = []
    _add(G, graph_data.get("nodes", []), graph_data.get("edges", []), "", None, notes, graph_data.get("_part_of"))
    if depth is not None:
        collapse(G, int(depth))
    return G, "; ".join(notes)
