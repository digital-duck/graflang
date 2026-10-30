"""Elaboration: a template applied to a graph of things (design 13.3 item 2).

A workflow with an `elaborate:` block turns a small graph of things (concepts, sections, files...) into a workflow:
one use of a part per thing, and the things' edges become ordering (and, if asked, data) between the uses.

    resources: {parts: {section: ./parts/section.graph.yaml}}
    elaborate:
      part: parts.section                       # the template: a part (see parts.py)
      over: ./concepts.yaml                     # a file with {nodes: [{id, ...attributes}], edges: [{source, target}]}, or the same inline
      with: {concept: title}                    # part input <- the thing's attribute (a literal default on that use)
      shared: [audience]                        # workflow inputs passed to every use (same name)
      pass: {from: text, to: context}           # an edge a -> b also binds a's output `text` to b's input `context`
      result: text                              # the part output collected (default: its first); the workflow output is
                                                #   one object, keyed by thing id

An edge `a -> b` means b runs after a. Things with no incoming edge start together (a FORK); a thing with several incoming
edges waits for all of them (a JOIN, which also bundles their `pass` values into one object keyed by the sources' ids). The
workflow's first output receives the object of every thing's result once all have finished. The result is ordinary nodes
and edges, so validation, the runtime and `graf vis` need to know nothing about elaboration; `graf expand` shows them.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import networkx as nx
from ruamel.yaml import YAML

from .parts import PartError, _interface, _load_part

ID = re.compile(r"^[A-Za-z0-9_]+$")
ENTRY, EXIT, START, DONE = "wf_entry", "wf_exit", "elab_start", "elab_done"


def _things(spec: Any, base: Path) -> Tuple[List[Dict], List[Dict]]:
    if isinstance(spec, (str, Path)):
        path = (base / spec).resolve()
        if not path.is_file():
            raise PartError(f"elaborate.over: {path} not found")
        spec = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not isinstance(spec.get("nodes"), list) or not spec["nodes"]:
        raise PartError("elaborate.over needs a non-empty `nodes:` list (and optionally `edges:`)")
    nodes, edges = spec["nodes"], spec.get("edges") or []
    ids = []
    for n in nodes:
        if not isinstance(n, dict) or "id" not in n:
            raise PartError(f"elaborate.over: every node needs an id, got {n!r}")
        nid = str(n["id"])
        if not ID.match(nid) or nid in (ENTRY, EXIT, START, DONE) or nid.startswith("elab_"):
            raise PartError(f"elaborate.over: node id {nid!r} must be letters, digits and underscores, and not reserved")
        ids.append(nid)
    if len(set(ids)) != len(ids):
        raise PartError(f"elaborate.over: duplicate node ids in {ids}")
    for e in edges:
        if str(e.get("source")) not in ids or str(e.get("target")) not in ids:
            raise PartError(f"elaborate.over: edge {e!r} names an unknown node")
    return nodes, edges


def elaborate(graph_data: Dict[str, Any]) -> None:
    """Replace the `elaborate:` block by the nodes and edges it describes. Does nothing without one."""
    cfg = graph_data.pop("elaborate", None)
    if cfg is None:
        return
    base = Path(graph_data.get("_source_dir", "."))
    wf = graph_data.get("workflow", {})
    inputs = [i["name"] for i in wf.get("inputs", [])]
    outputs = [o["name"] for o in wf.get("outputs", [])]
    if not outputs:
        raise PartError("elaborate needs a workflow output to receive the results")
    pname = str(cfg.get("part", "")).partition(".")[2]
    rel = (graph_data.get("resources", {}).get("parts") or {}).get(pname)
    if not cfg.get("part", "").startswith("parts.") or rel is None:
        raise PartError(f"elaborate.part {cfg.get('part')!r} is not listed under resources.parts")
    part_inputs, out_map, in_map, _, _ = _interface(_load_part((base / rel).resolve(), ()), pname)
    part_outs = sorted(set(out_map.values()))
    result = cfg.get("result") or part_outs[0]
    if result not in part_outs:
        raise PartError(f"elaborate.result {result!r} is not an output of the part (it has {part_outs})")
    mapping, shared, pas = cfg.get("with") or {}, list(cfg.get("shared") or []), cfg.get("pass")
    for name in [*mapping, *shared, *([pas["to"]] if pas else [])]:
        if name not in part_inputs:
            raise PartError(f"elaborate: {name!r} is not an input of the part (it has {sorted(part_inputs)})")
    for name in shared:
        if name not in inputs:
            raise PartError(f"elaborate.shared: {name!r} is not a workflow input (have {inputs})")
    if pas and pas["from"] not in part_outs:
        raise PartError(f"elaborate.pass.from {pas['from']!r} is not an output of the part (it has {part_outs})")

    things, edges = _things(cfg.get("over"), base)
    D = nx.DiGraph()
    D.add_nodes_from(str(n["id"]) for n in things)
    D.add_edges_from((str(e["source"]), str(e["target"])) for e in edges)
    if not nx.is_directed_acyclic_graph(D):
        raise PartError("elaborate.over has a cycle: " + " -> ".join(c for c, _ in nx.find_cycle(D)))

    nodes: List[Dict] = [{"id": ENTRY, "type": "INPUT", "ports": ["entry", *[f"out_{i}" for i in inputs]]}]
    out: List[Dict] = []
    bind = lambda a, b: out.append({"source": a, "target": b, "type": "binds"})
    trig = lambda a, b: out.append({"source": a, "target": b, "type": "triggers"})

    for t in things:
        nid = str(t["id"])
        defaults = {}
        for pin, attr in mapping.items():
            if attr in t:
                defaults[f"in_{pin}"] = t[attr]
            elif "default" not in part_inputs[pin]:
                raise PartError(f"elaborate: thing {nid!r} has no attribute {attr!r} for the input {pin!r}")
        ports = ["trigger", "complete", *[f"in_{p}" for p in [*mapping, *shared, *([pas["to"]] if pas else [])]], f"out_{result}"]
        if pas:
            ports.append(f"out_{pas['from']}")
        node: Dict[str, Any] = {"id": nid, "type": "SUBGRAPH", "ports": list(dict.fromkeys(ports)), "config": {"part": cfg["part"]}}
        if defaults:
            node["config"]["phases"] = {"pre": {"defaults": defaults}}
        nodes.append(node)
        for name in shared:
            bind(f"{ENTRY}.out_{name}", f"{nid}.in_{name}")

    roots = [n for n in D if D.in_degree(n) == 0]
    if len(roots) == 1:
        trig(f"{ENTRY}.entry", f"{roots[0]}.trigger")
    else:
        nodes.append({"id": START, "type": "FORK", "ports": ["trigger", *[f"go_{r}" for r in roots]]})
        trig(f"{ENTRY}.entry", f"{START}.trigger")
        for r in roots:
            trig(f"{START}.go_{r}", f"{r}.trigger")
    for nid in D:
        preds = sorted(D.predecessors(nid))
        if len(preds) == 1:
            trig(f"{preds[0]}.complete", f"{nid}.trigger")
            if pas:
                bind(f"{preds[0]}.out_{pas['from']}", f"{nid}.in_{pas['to']}")
        elif preds:
            jid = f"elab_in_{nid}"
            jports = ["trigger", "complete", *([*[f"in_{p}" for p in preds], "out_args"] if pas else [])]
            nodes.append({"id": jid, "type": "JOIN", "ports": jports})
            for p in preds:
                trig(f"{p}.complete", f"{jid}.trigger")
                if pas:
                    bind(f"{p}.out_{pas['from']}", f"{jid}.in_{p}")
            trig(f"{jid}.complete", f"{nid}.trigger")
            if pas:
                bind(f"{jid}.out_args", f"{nid}.in_{pas['to']}")

    sinks = [n for n in D if D.out_degree(n) == 0]
    ids = sorted(D)
    nodes.append({"id": DONE, "type": "JOIN", "ports": ["trigger", "complete", *[f"in_{i}" for i in ids], "out_results"]})
    for s in sinks:
        trig(f"{s}.complete", f"{DONE}.trigger")
    for i in ids:
        bind(f"{i}.out_{result}", f"{DONE}.in_{i}")
    nodes.append({"id": EXIT, "type": "OUTPUT", "ports": ["trigger", "exit", f"in_{outputs[0]}"]})
    trig(f"{DONE}.complete", f"{EXIT}.trigger")
    bind(f"{DONE}.out_results", f"{EXIT}.in_{outputs[0]}")

    graph_data["nodes"] = nodes + list(graph_data.get("nodes") or [])
    graph_data["edges"] = out + list(graph_data.get("edges") or [])
