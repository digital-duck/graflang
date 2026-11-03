"""Named subgraphs ("parts"): a workflow file used as a node inside another workflow (design §13.3, abstraction).

A part is an ordinary workflow file: a `workflow:` header whose inputs and outputs are its interface, one INPUT node and one or more
OUTPUT nodes (a branching workflow ends each branch in its own OUTPUT; the use node's `complete` fires from whichever was reached,
and an output declared by several of them takes the value of the one that ran), and the nodes between. Another workflow lists it under `resources.parts` and uses it as a `SUBGRAPH` node:

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

A part may also be named instead of located: `resources: {parts: {guard: "cookbook:guardrail"}}` finds the recipe in the work area
(`apps:`, `cookbook:` or `solvers:`), and `cookbook:guardrail@3fa9c01b2d4e` pins it to the hash `graf parts` prints, so a later change to
the recipe is reported instead of silently changing the graphs built on it.

A `file` path of a QUERY or EMIT inside a part is read relative to the *part's* folder (its bundled data, its own output folder), not the
folder of the graph that uses it: it is made absolute when the part is expanded, and the part's folder is added to the node's
`allow_dirs`. A path that resolves anywhere else (outside the part's folder and the using graph's folder) is refused by `graf validate`, so
composing never gives a part more reach than its folder plus what the using graph allows. A path that arrives on a port (`in_file`) is
the using graph's business and is read relative to the using graph. Other paths inside a part's nodes (a subprocess command, a parser
file) are still left as written, so they are read relative to the graph that uses the part; write them so that works, or make them absolute.
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


def _interface(part: Dict, name: str) -> Tuple[Dict[str, Dict], Dict[str, Dict[str, str]], Dict[str, str], Dict, List[Dict]]:
    """(inputs by name, {OUTPUT node id: its in_ port -> output name}, INPUT out_ port -> input name, INPUT node, OUTPUT nodes)."""
    wf = part["workflow"]
    inputs = {p["name"]: p for p in wf.get("inputs", [])}
    outputs = [p["name"] for p in wf.get("outputs", [])]
    entries = [n for n in part["nodes"] if n["type"] == "INPUT"]
    exits = [n for n in part["nodes"] if n["type"] == "OUTPUT"]
    if len(entries) != 1 or not exits:
        raise PartError(f"part {name!r} needs exactly one INPUT node and at least one OUTPUT node, found {len(entries)} and {len(exits)}")
    out_maps: Dict[str, Dict[str, str]] = {}
    for node in exits:
        in_ports = [p for p in _names(node["ports"]) if p.startswith("in_")]
        out_maps[node["id"]] = {in_ports[0]: outputs[0]} if len(in_ports) == 1 and len(outputs) == 1 else {p: p[3:] for p in in_ports}
        bad = sorted(set(out_maps[node["id"]].values()) - set(outputs))
        if bad:
            raise PartError(f"part {name!r}: its OUTPUT node {node['id']!r} takes {bad}, which workflow.outputs does not declare")
    in_map = {p: p[4:] for p in _names(entries[0]["ports"]) if p.startswith("out_")}
    bad = sorted(set(in_map.values()) - set(inputs))
    if bad:
        raise PartError(f"part {name!r}: its INPUT node offers {bad}, which workflow.inputs does not declare")
    return inputs, out_maps, in_map, entries[0], exits


ROOTS = ("apps", "cookbook", "solvers", "pocketflow")


def folder_hash(folder: Path) -> str:
    """A short hash of a recipe's files (graph, prompts, policies, procedures; not `output/`), to pin a part to the version you tried."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted(p for p in folder.rglob("*") if p.is_file() and not (set(p.relative_to(folder).parts) & {"output", "__pycache__", ".git"})
                    and p.suffix in (".yaml", ".yml", ".md", ".cedar", ".spl", ".json", ".py", ".txt")):
        h.update(f.relative_to(folder).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:12]


def named_part(ref: str) -> Path:
    """`cookbook:guardrail`, `apps:my_flow`, `solvers:x` or `pocketflow:rag` (optionally `@<hash>` to pin it) -> the recipe's graph file in the work area.

    The roots are the work area's (`~/.graflang/apps`, `cookbook`, `solvers`, `pocketflow`); `cookbook:` also finds the checkout's own cookbook. A
    pinned recipe that has changed since the hash was taken is refused, and the message gives the new hash."""
    from .. import workspace
    spec, _, pin = ref.partition("@")
    root, _, name = spec.partition(":")
    if root not in ROOTS or not name or not all(c.isalnum() or c in "_-" for c in name):
        raise PartError(f"part reference {ref!r}: write <root>:<recipe> with root one of {', '.join(ROOTS)}")
    homes = {"apps": [workspace.apps_dir()], "solvers": [workspace.solvers_dir()], "pocketflow": [workspace.pocketflow_dir()],
             "cookbook": [workspace.default_src_dir(), *([c] if (c := workspace.find_repo_cookbook()) else [])]}[root]
    folder = next((h / name for h in homes if (h / name).is_dir()), None)
    if folder is None:
        raise PartError(f"part reference {ref!r}: no recipe {name!r} under {', '.join(str(h) for h in homes)}")
    graph = folder / f"{name}.graph.yaml"
    if not graph.is_file():
        graphs = sorted(folder.glob("*.graph.yaml"))
        if len(graphs) != 1:
            raise PartError(f"part reference {ref!r}: {folder} has no {name}.graph.yaml")
        graph = graphs[0]
    if pin and folder_hash(folder) != pin:
        raise PartError(f"part reference {ref!r}: the recipe changed since it was pinned (now @{folder_hash(folder)})")
    return graph.resolve()


def part_file(rel: str, base: Path) -> Path:
    """The file a `resources.parts` entry names: a path relative to the using graph's folder, or a named recipe (`cookbook:guardrail`)."""
    rel = str(rel)
    if rel.partition(":")[0] in ROOTS and not rel.startswith(("/", ".")):
        return named_part(rel)
    return (base / rel).resolve()


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
    part_path = part_file(rel, base)
    part = _load_part(part_path, stack)
    inputs, out_maps, in_map, entry, exits = _interface(part, pname)
    out_names = {o for m in out_maps.values() for o in m.values()}

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
        if name not in out_names:
            raise PartError(f"{where}: port out_{name} is not an output of the part (it has {sorted(out_names)})")
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

    from .partinfo import capabilities, check_policy
    try:
        parent["_parts_calls"] = check_policy(capabilities(part["nodes"]), (parent.get("workflow") or {}).get("parts_policy"),
                                              where, parent.get("_parts_calls", 0))
    except ValueError as e:
        raise PartError(str(e)) from None

    prefix = f"{uid}{SEP}"
    taken = {n["id"] for n in nodes}
    inner = [n for n in part["nodes"] if n is not entry and n not in exits]
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
            if cfg.get("llm") and node.get("type") == "GENERATE" and not cfg_.get("llm"):
                cfg_["llm"] = cfg["llm"]                     # `llm:` on the use: the LLM of the part's GENERATE nodes that name none
            for key, kind_ in REF_KEYS:
                if key in cfg_:
                    cfg_[key] = f"{kind_}.{prefix}{str(cfg_[key]).partition('.')[2]}"
            body = cfg_.get("subgraph")
            if isinstance(body, dict):
                body["nodes"] = [_rewrite_refs(b, prefix) for b in body.get("nodes", [])]
        return node

    new_nodes = [_anchor_paths(rewrite(n), part_dir) for n in inner]
    members = parent.setdefault("_part_of", {})                      # for `graf vis`: which use each copied node came from
    members.update({n["id"]: (uid, pname) for n in new_nodes})

    p_edges = part["edges"]
    entry_id, exit_ids = entry["id"], {x["id"] for x in exits}

    def end(ref: str) -> Tuple[str, str]:
        node, _, port = ref.partition(".")
        return node, port

    # part-internal edges
    new_edges: List[Dict] = []
    for e in p_edges:
        (sn, sp), (tn, tp) = end(e["source"]), end(e["target"])
        if sn in {entry_id, *exit_ids} or tn in {entry_id, *exit_ids}:
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
                if tn in exit_ids:
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
    finishers = [(end(x["source"])) for x in p_edges if x["type"] == "triggers" and end(x["target"])[0] in exit_ids and end(x["target"])[1] == "trigger"]
    for e in parent_out:
        if e["type"] == "triggers":
            for (m, p) in finishers:
                new_edges.append({"source": f"{prefix}{m}.{p}", "target": e["target"], "type": "triggers"})
        else:
            name = end(e["source"])[1][4:]
            sources = [x for x in p_edges if x["type"] == "binds" and end(x["target"])[0] in exit_ids
                       and out_maps[end(x["target"])[0]].get(end(x["target"])[1]) == name]
            for x in sources:
                m, p = end(x["source"])
                if m == entry_id:
                    raise PartError(f"{where}: output {name!r} comes straight from the part's INPUT; give it a node in between")
                new_edges.append({"source": f"{prefix}{m}.{p}", "target": e["target"], "type": "binds"})

    # an output that promises a shape (`schema:` on workflow.outputs) is checked where it is produced
    for decl in part["workflow"].get("outputs", []):
        schema = decl.get("schema")
        if schema is None:
            continue
        try:
            from jsonschema import Draft202012Validator
            Draft202012Validator.check_schema(schema)
        except Exception as e:                                       # noqa: BLE001 - jsonschema's own error types
            raise PartError(f"{where}: output {decl['name']!r}: schema is not a JSON Schema: {getattr(e, 'message', e)}") from None
        for x in p_edges:
            ex = end(x["target"])[0]
            if x["type"] == "binds" and ex in exit_ids and out_maps[ex].get(end(x["target"])[1]) == decl["name"]:
                m, p = end(x["source"])
                node = next((n for n in new_nodes if n["id"] == prefix + m), None)
                firsts = [q for q in _names(node["ports"]) if q.startswith("out_")] if node else []
                if node is None or not firsts or firsts[0] != p:
                    raise PartError(f"{where}: output {decl['name']!r} has a schema but is not the first result of the node that makes it ({m!r}); "
                                    "give it a node of its own that makes only this result")
                post = node.setdefault("config", {}).setdefault("phases", {}).setdefault("post", {})
                post.setdefault("out_schema", schema)

    kept = [n for n in nodes if n["id"] != uid]
    return kept + new_nodes, rest + new_edges


PATH_NODES = ("QUERY", "EMIT")          # nodes whose `file` is a path that belongs to the part that wrote it


def _anchor_paths(node: Dict, part_dir: Path) -> Dict:
    """Make a QUERY's or EMIT's static `file` absolute, relative to the part's folder, and let the node reach that folder (`allow_dirs`).
    Done only here, at expansion: a graph file cannot ask for a folder of its own, so a part cannot widen what it may reach."""
    cfg = node.get("config")
    if isinstance(cfg, dict):
        if node.get("type") in PATH_NODES and isinstance(cfg.get("file"), str) and cfg["file"].strip():
            cfg["file"] = str((part_dir / cfg["file"]).resolve())
            cfg["allow_dirs"] = list(dict.fromkeys([*(cfg.get("allow_dirs") or []), str(part_dir.resolve())]))
        body = cfg.get("subgraph")
        if isinstance(body, dict):
            body["nodes"] = [_anchor_paths(b, part_dir) for b in body.get("nodes", [])]
    return node


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
    if "elaborate" in graph_data and "expand" not in graph_data:
        graph_data["expand"] = graph_data.pop("elaborate")      # the key's first name
    if "expand" in graph_data:
        from .expand import expand_things
        expand_things(graph_data)
    if not has_parts(graph_data.get("nodes", [])):
        return
    base = Path(base_dir or graph_data.get("_source_dir", "."))
    graph_data["nodes"], graph_data["edges"] = _flatten_scope(graph_data, graph_data["nodes"], graph_data.get("edges", []), base, _stack)
