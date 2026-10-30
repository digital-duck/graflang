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
    "GUARD": "#e5484d", "MUTATE": "#e5484d", "RECOVER": "#e5484d",
    "SOLVE": "#2fa84f", "QUERY": "#2fa84f", "CONTEXT": "#2fa84f", "OBSERVE": "#2fa84f",
}
OTHER_COLOR = "#8a8f98"
CONFIG_KEYS = ("prompt_ref", "procedure_ref", "condition", "model", "policy_ref", "policy_refs", "expression", "temperature")


def color(node_type: str) -> str:
    return TYPE_COLORS.get(node_type, OTHER_COLOR)


LABEL_CHARS = 36


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
        lines.append("prompt_inline: " + str(cfg["prompt_inline"]).strip().splitlines()[0][:60])
    lines.append("ports: " + ", ".join(node.get("ports", [])))
    return "\n".join(lines)


def _edge_label(etype: str, sport: str, tport: str) -> str:
    if etype == "binds":
        return sport[4:] if sport.startswith("out_") else sport
    return "" if sport in ("complete", "entry") else sport


def _add(G: nx.MultiDiGraph, nodes: List[Dict], edges: List[Dict], prefix: str, parent: str | None,
         notes: List[str]) -> None:
    ids = {}
    for n in nodes:
        qid = prefix + n["id"]
        ids[n["id"]] = qid
        G.add_node(qid, label=display_label(n), kind=n["type"], color=color(n["type"]), info=_info(n),
                   **({"parent": parent} if parent else {}))
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


def build(graph_data: Dict[str, Any]) -> Tuple[nx.MultiDiGraph, str]:
    """The workflow as a graph, and a one-line note on anything that could not be drawn."""
    G = nx.MultiDiGraph(name=graph_data.get("workflow", {}).get("name", "workflow"))
    notes: List[str] = []
    _add(G, graph_data.get("nodes", []), graph_data.get("edges", []), "", None, notes)
    return G, "; ".join(notes)
