"""Group: turn a selection of nodes into a composite, a part in a subfolder (design: docs/DEV/DESIGN/graflang-layers.md, sections 3 and 6).

`group(data, ids, name)` works on a long-form graph (plain dicts) and returns the new parent graph, the part's graph and the resource
files the part needs. It never touches the disk (`write_group` does that), and it refuses a selection whose boundary is not clean:

- one entry: every `triggers` edge from outside lands on one selected node's `trigger` port;
- one way out: every `triggers` edge that leaves goes to the same outside nodes (the part has one `complete`);
- data across the boundary becomes the part's inputs and outputs, one per distinct outside source / inside source.

The result has the same behaviour as the original once flattened (`parts.py` expands a use back into `<use>__<node>`).
"""
from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .parts import PATH_NODES, REF_KEYS

ENTRY, EXIT = "wf_entry", "wf_exit"
ROOTS_ = ("apps", "cookbook", "solvers", "pocketflow")


class GroupError(ValueError):
    pass


def _end(ref: str) -> Tuple[str, str]:
    node, _, port = ref.partition(".")
    return node, port


def _up(path: str) -> str:
    """A path written relative to the graph's folder, as it reads from a subfolder of it (absolute paths and named recipes stay)."""
    if path.startswith(("/", "~")) or path.partition(":")[0] in ROOTS_ and not path.startswith("."):
        return path
    return "../" + path[2:] if path.startswith("./") else "../" + path


def _reanchor(node: Dict) -> None:
    """The part's QUERY/EMIT `file` is read relative to the part's folder, so a path that meant the graph's folder gets a `../`."""
    cfg = node.get("config")
    if isinstance(cfg, dict):
        if node.get("type") in PATH_NODES and isinstance(cfg.get("file"), str) and cfg["file"].strip() and "{{" not in cfg["file"]:
            cfg["file"] = _up(cfg["file"])
        body = cfg.get("subgraph")
        if isinstance(body, dict):
            for b in body.get("nodes", []):
                _reanchor(b)


def _uses(nodes: List[Dict]) -> Set[str]:
    """The names (`parts.X` -> X) of the parts the nodes use, nested bodies included."""
    out: Set[str] = set()
    for n in nodes:
        cfg = n.get("config") or {}
        if n.get("type") == "SUBGRAPH" and isinstance(cfg.get("part"), str):
            out.add(cfg["part"].partition(".")[2])
        body = cfg.get("subgraph")
        if isinstance(body, dict):
            out |= _uses(body.get("nodes", []))
    return out


def _unique(name: str, taken: Set[str], node: str) -> str:
    for cand in (name, f"{node}_{name}"):
        if cand not in taken:
            return cand
    i = 2
    while f"{node}_{name}{i}" in taken:
        i += 1
    return f"{node}_{name}{i}"


def group(data: Dict[str, Any], ids: List[str], name: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[Tuple[str, str, str]]]:
    """(parent graph, part graph, files). `files` are (kind, name in the part, path in the parent's resources) for each prompt, procedure
    or policy a selected node uses: `write_group` copies them into the part's folder."""
    if not name or not name.replace("_", "").isalnum():
        raise GroupError("the composite's name uses letters, digits and underscores")
    nodes = {n["id"]: n for n in data["nodes"]}
    edges = data.get("edges", [])
    sel = list(dict.fromkeys(ids))
    if not sel:
        raise GroupError("select at least one node")
    for i in sel:
        if i not in nodes:
            raise GroupError(f"no node {i!r}")
        if nodes[i]["type"] in ("INPUT", "OUTPUT"):
            raise GroupError(f"{i!r} is the workflow's {nodes[i]['type']} node: it cannot go into a composite")
    if name in (data.get("resources", {}).get("parts") or {}) or name in nodes:
        raise GroupError(f"{name!r} is already used (a part or a node of this graph)")
    inside = set(sel)

    trig_in = [e for e in edges if e["type"] == "triggers" and _end(e["target"])[0] in inside and _end(e["source"])[0] not in inside]
    trig_out = [e for e in edges if e["type"] == "triggers" and _end(e["source"])[0] in inside and _end(e["target"])[0] not in inside]
    entries = {_end(e["target"])[0] for e in trig_in}
    if len(entries) != 1:
        raise GroupError("the selection needs exactly one entry (one selected node that outside nodes trigger); "
                         + ("nothing outside triggers it" if not entries else f"found {len(entries)}: {', '.join(sorted(entries))}"))
    entry_node = next(iter(entries))
    exits = sorted({e["source"] for e in trig_out})
    targets = {frozenset(e["target"] for e in trig_out if e["source"] == s) for s in exits}
    if len(targets) > 1:
        raise GroupError("the selection has several ways out that lead to different nodes; a composite has one `complete`")

    # data across the boundary
    in_edges = [e for e in edges if e["type"] == "binds" and _end(e["target"])[0] in inside and _end(e["source"])[0] not in inside]
    out_edges = [e for e in edges if e["type"] == "binds" and _end(e["source"])[0] in inside and _end(e["target"])[0] not in inside]
    in_names: Dict[str, str] = {}          # outside source ref -> input name
    for e in in_edges:
        src = e["source"]
        if src not in in_names:
            tn, tp = _end(e["target"])
            in_names[src] = _unique(tp[3:], set(in_names.values()), tn)
    out_names: Dict[str, str] = {}         # inside source ref -> output name
    for e in out_edges:
        src = e["source"]
        if src not in out_names:
            sn, sp = _end(src)
            out_names[src] = _unique(sp[4:], set(out_names.values()), sn)

    # the part
    wf_in = [{"name": nm, "type": "TEXT"} for nm in in_names.values()]
    wf_out = [{"name": nm, "type": "TEXT"} for nm in out_names.values()]
    inner_ids = set(sel)
    part_nodes = [{"id": ENTRY, "type": "INPUT", "ports": ["entry", *[f"out_{n}" for n in in_names.values()]]}]
    part_nodes += [copy.deepcopy(nodes[i]) for i in sel]
    for pn in part_nodes:
        _reanchor(pn)
    part_nodes.append({"id": EXIT, "type": "OUTPUT", "ports": ["trigger", "exit", *[f"in_{n}" for n in out_names.values()]]})
    part_edges = [copy.deepcopy(e) for e in edges if _end(e["source"])[0] in inner_ids and _end(e["target"])[0] in inner_ids]
    part_edges.append({"source": f"{ENTRY}.entry", "target": f"{entry_node}.trigger", "type": "triggers"})
    for s in exits:
        part_edges.append({"source": s, "target": f"{EXIT}.trigger", "type": "triggers"})
    for e in in_edges:
        part_edges.append({"source": f"{ENTRY}.out_{in_names[e['source']]}", "target": e["target"], "type": "binds"})
    for src, nm in out_names.items():
        part_edges.append({"source": src, "target": f"{EXIT}.in_{nm}", "type": "binds"})
    # a selected node with several incoming triggers from inside the selection keeps them; ones from outside are the use's trigger
    part = {"version": data.get("version", "1.0-graph"), "workflow": {"name": name, "inputs": wf_in, "outputs": wf_out},
            "nodes": part_nodes, "edges": part_edges}

    # resources the selected nodes use go with them
    files: List[Tuple[str, str, str]] = []
    res = data.get("resources", {}) or {}
    part_res: Dict[str, Dict[str, str]] = {}
    for i in sel:
        cfg = nodes[i].get("config") or {}
        for key, kind in REF_KEYS:
            if isinstance(cfg.get(key), str):
                rname = cfg[key].partition(".")[2]
                path = (res.get(kind) or {}).get(rname)
                if path is not None and (kind, rname, path) not in files:
                    files.append((kind, rname, str(path)))
                    part_res.setdefault(kind, {})[rname] = f"./{kind}/{Path(str(path)).name}"
    used_parts = _uses([nodes[i] for i in sel])
    for pname in sorted(used_parts):                          # parts the selection uses: the same recipe, its path read from the subfolder
        path = (res.get("parts") or {}).get(pname)
        if path is not None:
            part_res.setdefault("parts", {})[pname] = _up(str(path))
    if part_res:
        part["resources"] = part_res

    # the parent: the selection becomes one use
    use_ports = ["trigger", "complete", *[f"in_{n}" for n in in_names.values()], *[f"out_{n}" for n in out_names.values()]]
    use = {"id": name, "type": "SUBGRAPH", "ports": use_ports, "config": {"part": f"parts.{name}"}}
    first = min(data["nodes"].index(nodes[i]) for i in sel)
    parent = copy.deepcopy({k: v for k, v in data.items() if k not in ("nodes", "edges")})
    parent_nodes = [copy.deepcopy(n) for n in data["nodes"] if n["id"] not in inside]
    parent_nodes.insert(min(first, len(parent_nodes)), use)
    parent_edges = [copy.deepcopy(e) for e in edges if _end(e["source"])[0] not in inside and _end(e["target"])[0] not in inside]
    seen: Set[Tuple[str, str, str]] = set()

    def add(src: str, tgt: str, typ: str) -> None:
        if (src, tgt, typ) not in seen:
            seen.add((src, tgt, typ))
            parent_edges.append({"source": src, "target": tgt, "type": typ})
    for e in trig_in:
        add(e["source"], f"{name}.trigger", "triggers")
    for tgt in sorted(next(iter(targets), frozenset())):
        add(f"{name}.complete", tgt, "triggers")
    for e in in_edges:
        add(e["source"], f"{name}.in_{in_names[e['source']]}", "binds")
    for e in out_edges:
        add(f"{name}.out_{out_names[e['source']]}", e["target"], "binds")
    parent_res = parent.setdefault("resources", {})
    parent_res.setdefault("parts", {})[name] = f"./{name}/{name}.graph.yaml"
    still_used = {(kind, str(c.get(key)).partition(".")[2]) for n in parent_nodes for c in [n.get("config") or {}]
                  for key, kind in REF_KEYS if isinstance(c.get(key), str)}
    for kind, rname, _ in files:                             # a resource only the selection used leaves with it
        if (kind, rname) not in still_used and rname in (parent_res.get(kind) or {}):
            del parent_res[kind][rname]
            if not parent_res[kind]:
                del parent_res[kind]
    for pname in used_parts - _uses(parent_nodes):            # a part only the selection used leaves with it
        if pname in (parent_res.get("parts") or {}) and pname != name:
            del parent_res["parts"][pname]
    parent["nodes"], parent["edges"] = parent_nodes, parent_edges
    return parent, part, files


def write_group(folder: Path, name: str, part: Dict[str, Any], files: List[Tuple[str, str, str]], parent_dir: Path) -> Path:
    """Write the part to `<folder>/<name>/<name>.graph.yaml` and copy its resource files beside it. Refuses an existing folder."""
    from ..yamlfmt import dump_readable
    target = folder / name
    if target.exists():
        raise GroupError(f"{target} already exists: nothing was written")
    target.mkdir(parents=True)
    for kind, _, path in files:
        src = (parent_dir / path).resolve()
        dest = target / kind / src.name
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(src, dest)
    graph = target / f"{name}.graph.yaml"
    graph.write_text(dump_readable(part), encoding="utf-8")
    return graph
