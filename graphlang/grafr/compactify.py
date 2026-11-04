"""`graf compact`: the inverse of `graf expand`. A long-form workflow (`nodes:` / `edges:`) is rewritten as `steps:`.

The property it keeps: `expand(compact(g))` has the same nodes (id, type, ports, config) and the same edges as `g`.
It is checked, not hoped for: every pass is re-expanded and compared with the input, and a node whose step does not
come back exactly is kept in a `nodes:` list beside the steps (its edges in `edges:`). So the result is always right,
and sometimes less compact than hoped. Only these are not kept: the order of nodes and edges (steps come first, then
the leftovers), YAML comments and formatting, and any distinction between two spellings of the same graph.

Not one-to-one in the other direction (compact -> expand -> compact): several `steps:` can expand to one long form
(for example `on:` spelled out where it equals the default), so the compact text you get back is the canonical one.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .compact import ENTRY, ID, KINDS, RESERVED, RUN_CODE_OUTS, TYPES, CompactError, _build, expand, is_compact

UNTYPES = {v: k for k, v in TYPES.items() if k != "loop"}      # GENERATE -> generate; LOOP is handled apart


class NotCompactable(ValueError):
    pass


def _norm_node(n: Dict) -> str:
    n = copy.deepcopy(n)
    n["ports"] = sorted(n.get("ports", []))
    sub = (n.get("config") or {}).get("subgraph")
    if isinstance(sub, dict):                       # a loop body: the order of its nodes and edges is no more meaning
        sub["nodes"] = sorted((json.loads(_norm_node(x)) for x in sub.get("nodes", [])), key=lambda x: str(x.get("id")))
        sub["edges"] = [json.loads(e) for e in _norm_edges(sub.get("edges", []))]
    return json.dumps(n, sort_keys=True, default=str)


def _norm_edges(edges: List[Dict]) -> List[str]:
    return sorted({json.dumps(e, sort_keys=True, default=str) for e in edges})


def _is_io(p: str) -> bool:
    return p.startswith(("in_", "out_"))


def _ctrl(node: Dict) -> List[str]:
    return [p for p in node.get("ports", []) if not _is_io(p)]


def _pass_once(nodes: List[Dict], edges: List[Dict], inputs: List[str], outputs: List[str], root: bool,
          raw: set) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """One attempt: (steps, raw nodes, raw edges). `raw` ids are kept as nodes."""
    by_id = {n["id"]: n for n in nodes}
    cand = [n for n in nodes if n["id"] != ENTRY and n["id"] not in raw
            and isinstance(n.get("id"), str) and ID.match(n["id"]) and "__" not in n["id"]]
    ids = [n["id"] for n in cand]
    idset = set(ids)

    kinds: Dict[str, str] = {}
    outs: Dict[str, List[str]] = {}
    for n in cand:
        cfg = n.get("config") or {}
        t = n.get("type")
        if t == "LOOP":
            kind = "loop"
        elif t in UNTYPES:
            kind = UNTYPES[t]
            if kind == "generate" and not ("prompt_ref" in cfg or "prompt_inline" in cfg):
                kind = "node"
            if kind == "solve" and "expression" not in cfg:
                kind = "node"
            if kind in ("assert", "evaluate") and "condition" not in cfg:
                kind = "node"
            if kind == "guard" and "policy_ref" not in cfg:
                kind = "node"
            if kind == "use" and "part" not in cfg:
                kind = "node"
            if kind == "run_code" and not (isinstance(cfg.get("languages"), list) and cfg["languages"]):
                kind = "node"
        else:
            kind = "node"
        kinds[n["id"]] = kind
        if kind == "loop":
            outs[n["id"]] = list((cfg.get("outputs") or {}))
        else:
            outs[n["id"]] = [p[4:] for p in n.get("ports", []) if p.startswith("out_")]

    def src_ref(source: str) -> Optional[str]:
        node, _, port = source.partition(".")
        if node == ENTRY and root and port.startswith("out_") and port[4:] in inputs:
            return f"$in.{port[4:]}"
        if node in idset and port.startswith("out_") and port[4:] in outs[node] and kinds[node] != "output":
            return node if outs[node][0] == port[4:] else f"{node}.{port[4:]}"
        return None

    # binds: node -> port -> [source refs]; edges kept raw otherwise
    raw_edges: List[Dict] = []
    in_src: Dict[Tuple[str, str], List[str]] = {}
    in_edges: Dict[Tuple[str, str], List[Dict]] = {}
    ctrl_edges: Dict[str, List[Tuple[str, Dict]]] = {i: [] for i in ids}
    order = {i: k for k, i in enumerate(ids)}
    for e in edges:
        ok = False
        if set(e) == {"source", "target", "type"} and isinstance(e["source"], str) and isinstance(e["target"], str):
            tn, _, tp = e["target"].partition(".")
            if tn in idset:
                if e["type"] == "binds" and tp.startswith("in_") and tp in by_id[tn].get("ports", []):
                    ref = src_ref(e["source"])
                    if ref is not None:
                        in_src.setdefault((tn, tp), []).append(ref)
                        in_edges.setdefault((tn, tp), []).append(e)
                        ok = True
                elif e["type"] == "triggers" and tp == "trigger":
                    sn, _, sp = e["source"].partition(".")
                    if sn == ENTRY and root and sp == "entry":
                        ctrl_edges[tn].append(("$in", e))
                        ok = True
                    elif sn in idset and order[sn] < order[tn] and sp in _ctrl(by_id[sn])[1:]:
                        default = _ctrl(by_id[sn])[1] if len(_ctrl(by_id[sn])) > 1 else None
                        ctrl_edges[tn].append((sn if sp == default else f"{sn}.{sp}", e))
                        ok = True
        if not ok:
            raw_edges.append(e)

    # nodes whose step cannot be written go raw, with all their edges (done by the verify loop, but catch the obvious)
    bad: set = set()
    steps: List[Dict] = []
    used_edges: List[Dict] = []
    for idx, n in enumerate(cand):
        sid, kind, cfg = n["id"], kinds[n["id"]], copy.deepcopy(n.get("config") or {})
        ports = n.get("ports", [])
        if sid in bad:
            raw.add(sid)
            continue
        # arguments and what leaves config
        if kind == "generate":
            arg = cfg.pop("prompt_ref") if "prompt_ref" in cfg else cfg.pop("prompt_inline")
        elif kind == "solve":
            arg = cfg.pop("expression")
        elif kind in ("assert", "evaluate"):
            arg = cfg.pop("condition")
        elif kind == "guard":
            arg = cfg.pop("policy_ref")
        elif kind == "use":
            arg = cfg.pop("part")
        elif kind == "run_code":
            arg = cfg.pop("languages")
        elif kind == "fork":
            arg = [p for p in _ctrl(n) if p != "trigger"]
        elif kind == "join":
            arg = None
        elif kind == "output":
            arg = None
        elif kind == "loop":
            arg = cfg.pop("max_iterations", None)
        else:
            arg = n["type"]
        body: Dict[str, Any] = {}
        extra_ports = []
        outputs_spec: Dict = {}
        if kind == "loop":
            sub = cfg.pop("subgraph", None) or {}
            try:
                sub_steps, sub_nodes, sub_edges = lower(sub.get("nodes", []), sub.get("edges", []), [], [], root=False)
            except (NotCompactable, CompactError):
                raw.add(sid)
                continue
            if sub_nodes or sub_edges or not sub_steps or sub.keys() - {"nodes", "edges"}:
                raw.add(sid)
                continue
            body["loop"] = arg
            if "condition" in cfg:
                body["while"] = cfg.pop("condition")
            if "index_var" in cfg:
                body["index"] = cfg.pop("index_var")
            outputs_spec = cfg.pop("outputs", None) or {}
            body["steps"] = sub_steps
        else:
            body[kind] = arg
            if kind == "node":
                extra_ports = [p for p in _ctrl(n) if p not in ("trigger", "complete")]

        # inputs
        in_map: Dict[str, Any] = {}
        defaults = ((cfg.get("phases") or {}).get("pre") or {}).get("defaults") or {}
        for p in ports:
            if not p.startswith("in_"):
                continue
            name = p[3:]
            srcs = in_src.get((sid, p))
            if srcs:
                in_map[name] = srcs[0] if len(srcs) == 1 else list(dict.fromkeys(srcs))     # several writers: `[a, b]`
                used_edges += in_edges[(sid, p)]
                if p in defaults:                         # an edge and a default on one port: not expressible
                    bad.add(sid)
            elif p in defaults:
                v = defaults[p]
                if isinstance(v, dict) and set(v) == {"value"}:
                    v = {"value": v}
                elif isinstance(v, str) and (v.startswith("$") or v.partition(".")[0] in idset):
                    v = {"value": v}
                in_map[name] = v
            elif not root:
                in_map[name] = f"$loop.{name}"
            else:
                bad.add(sid)
        if sid in bad:
            raw.add(sid)
            continue
        for p in list(defaults):
            if p.startswith("in_") and p in ports and not in_src.get((sid, p)):
                del defaults[p]
        if "phases" in cfg:
            pre = cfg["phases"].get("pre")
            if isinstance(pre, dict) and "defaults" in pre and not pre["defaults"]:
                del pre["defaults"]
            if isinstance(pre, dict) and not pre:
                del cfg["phases"]["pre"]
            if not cfg["phases"]:
                del cfg["phases"]

        if kind == "output":
            if len(outputs) == 1 and list(in_map) == outputs:
                body["output"] = in_map[outputs[0]]
            else:
                body["output"] = in_map
        else:
            if in_map:
                body["in"] = in_map
            if kind == "loop":
                if outputs_spec:
                    body["out"] = _loop_out(outputs_spec)
            elif outs[sid] == (RUN_CODE_OUTS if kind == "run_code" else ["result"]):
                pass
            else:
                body["out"] = outs[sid][0] if len(outs[sid]) == 1 else list(outs[sid])
        if extra_ports:
            body["ports"] = extra_ports

        # control: `on:` unless it equals what expand adds by itself
        if kind != "join":
            sources = [s for s, _ in ctrl_edges[sid]]
            prev = ids_before(ids, raw, idx)
            if prev is None:
                implicit = ["$in"] if root else []
            else:
                pc = _ctrl(by_id[prev])
                implicit = [prev] if kinds[prev] != "fork" and len(pc) > 1 and pc[1] else None
                if kinds[prev] == "fork":
                    implicit = None
            if implicit is None or sorted(sources) != sorted(implicit):
                body["on"] = sources[0] if len(sources) == 1 else sources
            used_edges += [e for _, e in ctrl_edges[sid]]
        else:
            body[kind] = [s for s, _ in ctrl_edges[sid]]
            used_edges += [e for _, e in ctrl_edges[sid]]

        for k, v in cfg.items():
            if k in RESERVED or k in KINDS or (kind == "loop" and k in ("steps", "while", "index")):
                body.setdefault("config", {})[k] = v
            else:
                body[k] = v
        steps.append({sid: body})

    step_ids = {next(iter(s)) for s in steps}
    raw_nodes = [n for n in nodes if n["id"] != ENTRY and n["id"] not in step_ids]
    used = {json.dumps(e, sort_keys=True) for e in used_edges}
    leftover = [e for e in edges if json.dumps(e, sort_keys=True) not in used]
    # an edge into a raw node's port must stay raw too (it is, as it is not in used_edges)
    return steps, raw_nodes, leftover


def _pass(nodes: List[Dict], edges: List[Dict], inputs: List[str], outputs: List[str], root: bool,
          raw: set) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Run a pass again while it finds more nodes it must keep raw (edges to them change what the others can say)."""
    while True:
        before = len(raw)
        result = _pass_once(nodes, edges, inputs, outputs, root, raw)
        if len(raw) == before:
            return result


def ids_before(ids: List[str], raw: set, idx: int) -> Optional[str]:
    """The step that precedes position `idx` in the list of candidates that stay steps (raw ones are skipped)."""
    for j in range(idx - 1, -1, -1):
        if ids[j] not in raw:
            return ids[j]
    return None


def _loop_out(spec: Dict) -> Dict:
    out: Dict[str, Any] = {}
    for name, how in spec.items():
        (kind, ref), = how.items()
        conv = (lambda r: r.replace(".out_", ".", 1)) if kind != "fired" else (lambda r: r)
        out[name] = {kind: [conv(r) for r in ref] if isinstance(ref, list) else conv(ref)}
    return out


def lower(nodes: List[Dict], edges: List[Dict], inputs: List[str], outputs: List[str], root: bool
          ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """(steps, nodes, edges) for a long form, verified by expanding them again."""
    nodes = copy.deepcopy(nodes)
    edges = copy.deepcopy(edges)
    if root:
        entry = next((n for n in nodes if n.get("id") == ENTRY), None)
        want = sorted(["entry", *[f"out_{i}" for i in inputs]])
        if entry is None or entry.get("type") != "INPUT" or sorted(entry.get("ports", [])) != want:
            raise NotCompactable(f"the long form has no {ENTRY!r} INPUT node with ports {want}; not a form `steps:` can say")
    raw: set = set()
    want_nodes = {n["id"]: _norm_node(n) for n in nodes}
    want_edges = _norm_edges(edges)
    for _ in range(len(nodes) + 2):
        steps, raw_nodes, raw_edges = _pass(nodes, edges, inputs, outputs, root, raw)
        if not steps:
            raise NotCompactable("no node could be written as a step")
        blame: set = set()
        try:
            n2, e2 = _build(steps, inputs, outputs, root)
        except CompactError as ex:
            blame = set(re.findall(r"step '(\w+)'", str(ex)))
            if not blame:
                raise NotCompactable(str(ex))
        else:
            got_nodes = {n["id"]: _norm_node(n) for n in n2 + raw_nodes}
            if root:
                got_nodes[ENTRY] = want_nodes[ENTRY]
            for i in set(want_nodes) | set(got_nodes):
                if want_nodes.get(i) != got_nodes.get(i):
                    blame.add(i)
            for e in set(_norm_edges(e2 + raw_edges)) ^ set(want_edges):
                d = json.loads(e)
                for end in (d.get("source"), d.get("target")):
                    blame.add(str(end).partition(".")[0])
            blame -= {ENTRY}
        if not blame:
            return steps, raw_nodes, raw_edges
        step_ids = {next(iter(s)) for s in steps}
        new = blame & step_ids
        if not new:
            raise NotCompactable(f"round trip differs at {sorted(blame)}")
        raw |= new
    raise NotCompactable("could not settle on a compact form")


def compactify(data: Dict) -> Tuple[Dict, Dict[str, Any]]:
    """(compact graph, report). The graph is the long form of `data` written with `steps:` as far as is exact."""
    if is_compact(data):
        data = expand(data)
    wf = data.get("workflow")
    if not isinstance(wf, dict) or "nodes" not in data:
        raise NotCompactable("needs a long-form graph with a `workflow:` block and `nodes:`")
    inputs = [i["name"] for i in wf.get("inputs", [])]
    outputs = [o["name"] for o in wf.get("outputs", [])]
    steps, raw_nodes, raw_edges = lower(data["nodes"], data.get("edges", []), inputs, outputs, root=True)
    out = {k: v for k, v in data.items() if k not in ("nodes", "edges")}
    out["steps"] = steps
    if raw_nodes:
        out["nodes"] = raw_nodes
    if raw_edges:
        out["edges"] = raw_edges
    order = [k for k in ("version", "workflow", "resources", "steps", "nodes", "edges") if k in out]
    out = {**{k: out[k] for k in order}, **{k: v for k, v in out.items() if k not in order}}
    total = len(data["nodes"]) - 1
    report = {"steps": len(steps), "nodes_total": total, "nodes_kept": len(raw_nodes), "edges_kept": len(raw_edges),
              "edges_total": len(data.get("edges", []))}
    return out, report
