"""Named subgraphs ("parts"): a workflow file used as a node inside another workflow (design §13.3, abstraction).

A part is an ordinary workflow file: a `workflow:` header whose inputs and outputs are its interface, an INPUT node and an OUTPUT
node, and the nodes between. Another workflow lists it under `resources.parts` and uses it as a `SUBGRAPH` node:

    resources: {parts: {review: ./parts/review.graph.yaml}}
    nodes:
      - id: critique
        type: SUBGRAPH
        config: {part: parts.review}
        ports: [trigger, complete, in_essay, in_tone, out_feedback]      # trigger/complete, one in_ per part input, one out_ per part output

The use is checked against the part's interface (every `in_` is an input of the part, every input without a default is bound, every
`out_` is an output, types assignable) and then *expanded in place*: the part's nodes join the graph with ids `critique__draft`, its
INPUT and OUTPUT nodes disappear into direct wires, and its prompts, procedures and policies are added to the resources under
prefixed names. After that nothing else knows parts exist: `graf validate`, the race check, `graf vis`, concurrent mode, checkpoints and the
rest see one flat graph, and `graf expand` prints it. A part may use parts; a part that uses itself is an error. A part used twice is
expanded twice, each copy with its own state.

Paths inside a part's nodes other than resource references (a subprocess command, a parser file) are left as written, so they are read
relative to the graph that uses the part; write them so that works, or make them absolute.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml import YAML

from .compact import expand as expand_compact, is_compact
from .ports import INPUT_TYPES, assignable

SEP = "__"
REF_KEYS = (("prompt_ref", "prompts"), ("procedure_ref", "procedures"), ("policy_ref", "policies"))
KINDS = ("prompts", "procedures", "policies")


class PartError(ValueError):
    pass


def has_parts(nodes: List[Dict]) -> bool:
    for n in nodes:
        if n.get("type") == "SUBGRAPH":
            return True
        body = n.get("config", {}).get("subgraph")
        if isinstance(body, dict) and has_parts(body.get("nodes", [])):
            return True
    return False


def _names(ports: Any) -> List[str]:
    return list(ports) if isinstance(ports, (list, tuple)) else list(ports)


def _load_part(path: Path, stack: Tuple[Path, ...]) -> Dict:
    if path in stack:
        chain = " -> ".join(p.name for p in (*stack, path))
        raise PartError(f"a part cannot use itself: {chain}")
    if not path.is_file():
        raise PartError(f"part file not found: {path}")
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if is_compact(data):
        data = expand_compact(data)
    if not isinstance(data, dict) or "workflow" not in data or "nodes" not in data:
        raise PartError(f"{path.name} is not a workflow file (needs workflow:, nodes:, edges:)")
    data.setdefault("edges", [])
    data["_source_dir"] = str(path.parent)
    flatten_parts(data, _stack=(*stack, path))
    return data


def _interface(part: Dict, name: str) -> Tuple[Dict[str, Dict], Dict[str, str], Dict[str, str], Dict, Dict]:
    """(inputs by name, OUTPUT in_ port -> output name, INPUT out_ port -> input name, INPUT node, OUTPUT node)."""
    wf = part["workflow"]
    inputs = {p["name"]: p for p in wf.get("inputs", [])}
    outputs = [p["name"] for p in wf.get("outputs", [])]
    entries = [n for n in part["nodes"] if n["type"] == "INPUT"]
    exits = [n for n in part["nodes"] if n["type"] == "OUTPUT"]
    if len(entries) != 1 or len(exits) != 1:
        raise PartError(f"part {name!r} needs exactly one INPUT and one OUTPUT node, found {len(entries)} and {len(exits)}")
    in_ports = [p for p in _names(exits[0]["ports"]) if p.startswith("in_")]
    if len(in_ports) == 1 and len(outputs) == 1:
        out_map = {in_ports[0]: outputs[0]}
    else:
        out_map = {p: p[3:] for p in in_ports}
    bad = sorted(set(out_map.values()) - set(outputs))
    if bad:
        raise PartError(f"part {name!r}: its OUTPUT node takes {bad}, which workflow.outputs does not declare")
    in_map = {p: p[4:] for p in _names(entries[0]["ports"]) if p.startswith("out_")}
    bad = sorted(set(in_map.values()) - set(inputs))
    if bad:
        raise PartError(f"part {name!r}: its INPUT node offers {bad}, which workflow.inputs does not declare")
    return inputs, out_map, in_map, entries[0], exits[0]


def _port_type(node: Dict, port: str) -> str:
    spec = node.get("ports")
    if isinstance(spec, dict):
        t = spec.get(port, "ANY")
        return str(t.get("type", "ANY") if isinstance(t, dict) else t)
    return "ANY"


def _expand_use(parent: Dict, nodes: List[Dict], edges: List[Dict], use: Dict, base: Path, stack: Tuple[Path, ...]) -> Tuple[List[Dict], List[Dict]]:
    uid, cfg = use["id"], use.get("config", {})
    ref = cfg.get("part", "")
    kind, _, pname = ref.partition(".")
    rel = (parent.get("resources", {}).get("parts") or {}).get(pname)
    if kind != "parts" or rel is None:
        raise PartError(f"SUBGRAPH {uid!r}: config.part {ref!r} is not listed under resources.parts")
    part_path = (base / rel).resolve()
    part = _load_part(part_path, stack)
    inputs, out_map, in_map, entry, exit_ = _interface(part, pname)

    ports = _names(use["ports"])
    ins = {p[3:]: p for p in ports if p.startswith("in_")}
    outs = {p[4:]: p for p in ports if p.startswith("out_")}
    where = f"SUBGRAPH {uid!r} (part {pname!r})"
    if "trigger" not in ports or "complete" not in ports:
        raise PartError(f"{where}: needs the ports trigger and complete")
    for name in ins:
        if name not in inputs:
            raise PartError(f"{where}: port in_{name} is not an input of the part (it has {sorted(inputs)})")
    for name in outs:
        if name not in set(out_map.values()):
            raise PartError(f"{where}: port out_{name} is not an output of the part (it has {sorted(set(out_map.values()))})")
    bound_in = {e["target"].partition(".")[2] for e in edges if e["type"] == "binds" and e["target"].partition(".")[0] == uid}
    literals = {k[3:]: v for k, v in (cfg.get("phases", {}).get("pre", {}).get("defaults") or {}).items()}   # `in: {tone: formal}` in a compact use
    defaults = {name: literals[name] if name in literals else decl["default"] for name, decl in inputs.items() if name in literals or "default" in decl}
    for name, decl in inputs.items():
        if name in in_map.values() and f"in_{name}" not in bound_in and name not in defaults:
            raise PartError(f"{where}: input {name!r} of the part is not bound and has no default")
        declared = INPUT_TYPES.get(str(decl.get("type", "TEXT")).upper())
        mine = _port_type(use, f"in_{name}")
        if name in ins and declared and mine != "ANY" and not assignable(mine.split("!")[0].upper(), declared):
            raise PartError(f"{where}: in_{name} is {mine} but the part expects {declared}")

    prefix = f"{uid}{SEP}"
    taken = {n["id"] for n in nodes}
    inner = [n for n in part["nodes"] if n is not entry and n is not exit_]
    for n in inner:
        if prefix + n["id"] in taken:
            raise PartError(f"{where}: expanding it would create a second node {prefix + n['id']!r}")

    # resources: the part's files join the parent's under prefixed names, with absolute paths
    res = parent.setdefault("resources", {})
    part_dir = Path(part["_source_dir"])
    for k in KINDS:
        for name, path in (part.get("resources", {}).get(k) or {}).items():
            res.setdefault(k, {})[prefix + name] = str((part_dir / path).resolve())

    def rewrite(node: Dict) -> Dict:
        node = copy.deepcopy(node)
        node["id"] = prefix + node["id"]
        cfg_ = node.get("config")
        if isinstance(cfg_, dict):
            for key, kind_ in REF_KEYS:
                if key in cfg_:
                    cfg_[key] = f"{kind_}.{prefix}{str(cfg_[key]).partition('.')[2]}"
            body = cfg_.get("subgraph")
            if isinstance(body, dict):
                body["nodes"] = [_rewrite_refs(b, prefix) for b in body.get("nodes", [])]
        return node

    new_nodes = [rewrite(n) for n in inner]

    p_edges = part["edges"]
    entry_id, exit_id = entry["id"], exit_["id"]

    def end(ref: str) -> Tuple[str, str]:
        node, _, port = ref.partition(".")
        return node, port

    # part-internal edges
    new_edges: List[Dict] = []
    for e in p_edges:
        (sn, sp), (tn, tp) = end(e["source"]), end(e["target"])
        if sn in (entry_id, exit_id) or tn in (entry_id, exit_id):
            continue
        new_edges.append({**e, "source": f"{prefix}{sn}.{sp}", "target": f"{prefix}{tn}.{tp}"})

    parent_in = [e for e in edges if end(e["target"])[0] == uid]
    parent_out = [e for e in edges if end(e["source"])[0] == uid]
    rest = [e for e in edges if e not in parent_in and e not in parent_out]

    # control in: A.p -> use.trigger  +  part.entry -> N.trigger  =>  A.p -> use__N.trigger
    starts = [end(e["target"])[0] for e in p_edges if e["type"] == "triggers" and end(e["source"]) == (entry_id, "entry")]
    if not starts:
        raise PartError(f"{where}: the part's INPUT node triggers nothing")
    for e in parent_in:
        if e["type"] == "triggers":
            for n in starts:
                new_edges.append({"source": e["source"], "target": f"{prefix}{n}.trigger", "type": "triggers"})
        else:
            name = end(e["target"])[1][3:]
            targets = [x for x in p_edges if x["type"] == "binds" and end(x["source"]) == (entry_id, f"out_{name}")]
            for x in targets:
                tn, tp = end(x["target"])
                if tn == exit_id:
                    raise PartError(f"{where}: input {name!r} goes straight to the part's OUTPUT; give it a node in between")
                new_edges.append({"source": e["source"], "target": f"{prefix}{tn}.{tp}", "type": "binds"})
    # defaults of unbound inputs go to the nodes that read them
    for name, value in defaults.items():
        if f"in_{name}" not in bound_in:
            for x in p_edges:
                if x["type"] == "binds" and end(x["source"]) == (entry_id, f"out_{name}"):
                    tn, tp = end(x["target"])
                    target = next(n for n in new_nodes if n["id"] == prefix + tn)
                    target.setdefault("config", {}).setdefault("phases", {}).setdefault("pre", {}).setdefault("defaults", {})[tp] = value
    # control out: part.M.p -> OUTPUT.trigger  +  use.complete -> B.trigger  =>  use__M.p -> B.trigger
    finishers = [(end(x["source"])) for x in p_edges if x["type"] == "triggers" and end(x["target"]) == (exit_id, "trigger")]
    for e in parent_out:
        if e["type"] == "triggers":
            for (m, p) in finishers:
                new_edges.append({"source": f"{prefix}{m}.{p}", "target": e["target"], "type": "triggers"})
        else:
            name = end(e["source"])[1][4:]
            sources = [x for x in p_edges if x["type"] == "binds" and end(x["target"])[0] == exit_id and out_map.get(end(x["target"])[1]) == name]
            for x in sources:
                m, p = end(x["source"])
                if m == entry_id:
                    raise PartError(f"{where}: output {name!r} comes straight from the part's INPUT; give it a node in between")
                new_edges.append({"source": f"{prefix}{m}.{p}", "target": e["target"], "type": "binds"})

    kept = [n for n in nodes if n["id"] != uid]
    return kept + new_nodes, rest + new_edges


def _rewrite_refs(node: Dict, prefix: str) -> Dict:
    node = copy.deepcopy(node)
    cfg = node.get("config")
    if isinstance(cfg, dict):
        for key, kind in REF_KEYS:
            if key in cfg:
                cfg[key] = f"{kind}.{prefix}{str(cfg[key]).partition('.')[2]}"
        body = cfg.get("subgraph")
        if isinstance(body, dict):
            body["nodes"] = [_rewrite_refs(b, prefix) for b in body.get("nodes", [])]
    return node


def _flatten_scope(parent: Dict, nodes: List[Dict], edges: List[Dict], base: Path, stack: Tuple[Path, ...]) -> Tuple[List[Dict], List[Dict]]:
    for n in nodes:
        body = n.get("config", {}).get("subgraph")
        if isinstance(body, dict) and has_parts(body.get("nodes", [])):
            body["nodes"], body["edges"] = _flatten_scope(parent, body["nodes"], body.get("edges", []), base, stack)
    while True:
        use = next((n for n in nodes if n.get("type") == "SUBGRAPH"), None)
        if use is None:
            return nodes, edges
        nodes, edges = _expand_use(parent, nodes, edges, use, base, stack)


def flatten_parts(graph_data: Dict[str, Any], base_dir: Optional[Path] = None, _stack: Tuple[Path, ...] = ()) -> None:
    """Expand every SUBGRAPH node of the graph in place. Does nothing when there are none."""
    if not has_parts(graph_data.get("nodes", [])):
        return
    base = Path(base_dir or graph_data.get("_source_dir", "."))
    graph_data["nodes"], graph_data["edges"] = _flatten_scope(graph_data, graph_data["nodes"], graph_data.get("edges", []), base, _stack)
