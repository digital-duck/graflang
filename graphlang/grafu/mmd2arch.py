"""`graf util mmd2arch`: a Mermaid flowchart `.mmd` -> an architecture graph `.arch.yaml`; and the round-trip check.

The two converters are meant to be inverses, so a picture and its architecture can be shown to say the same thing:

    arch -> mmd -> arch      identical (`roundtrip_arch`): nothing the graph says is lost by drawing it
    mmd  -> arch -> mmd      the same picture (`roundtrip_mmd`): nothing the picture shows is lost by reading it

A `.mmd` written by `graf util arch2mmd` also carries an `%% arch-meta:` line with what a picture cannot show (package names, rules, group
style names, which dashed edges cross a network); a hand-written `.mmd` has none and gets the defaults. No dependency beyond PyYAML.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .arch2mmd import ArchError, to_mermaid, validate

_NODE = re.compile(r'^([A-Za-z]\w*)\s*\[\s*"(.*)"\s*\]\s*$')
_EDGE = re.compile(r'^([A-Za-z]\w*)\s*(-->|-\.->|~~~)\s*(?:\|\s*"?(.*?)"?\s*\|\s*)?([A-Za-z]\w*)\s*$')
_SUBGRAPH = re.compile(r'^subgraph\s+([A-Za-z]\w*)\s*\[\s*"?(.*?)"?\s*\]\s*$')
_CMD = re.compile(r"^<code>[^<]*</code>(?: / <code>[^<]*</code>)*$")
_TITLE = re.compile(r"^(\d+)\s*·\s*(.+)$")


def _unhtml_title(t: str) -> str:
    return t.replace("&nbsp;", " ").replace("#quot;", '"').strip()


def _props(text: str) -> dict:
    out = {}
    for part in text.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def parse(text: str) -> dict:
    """The structure of a Mermaid flowchart as a plain dict: subgraph tree, nodes (with their raw labels), edges, hints, classes, styles, meta."""
    ir: dict = {"layout": "dagre", "direction": "TB", "boxes": [], "nodes": {}, "edges": [], "hints": [], "classdefs": {}, "classes": {}, "styles": {}, "meta": {}}
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end:
            front = yaml.safe_load("\n".join(lines[1:end])) or {}
            ir["layout"] = ((front.get("config") or {}).get("layout")) or ir["layout"]
            lines = lines[end + 1:]
    stack: list[dict] = []
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith("%%"):
            m = re.match(r"^%%\s*arch-meta:\s*(\{.*\})\s*$", ln)
            if m:
                ir["meta"] = json.loads(m.group(1))
            continue
        if ln.startswith("flowchart") or ln.startswith("graph "):
            parts = ln.split()
            ir["direction"] = parts[1] if len(parts) > 1 else "TB"
        elif m := _SUBGRAPH.match(ln):
            box = {"id": m.group(1), "title": m.group(2), "direction": None, "children": [], "nodes": [], "parent": stack[-1]["id"] if stack else None}
            (stack[-1]["children"] if stack else ir["boxes"]).append(box)
            stack.append(box)
        elif ln == "end":
            if stack:
                stack.pop()
        elif ln.startswith("direction ") and stack:
            stack[-1]["direction"] = ln.split()[1]
        elif ln.startswith("classDef "):
            _, name, rest = ln.split(None, 2)
            ir["classdefs"][name] = _props(rest)
        elif ln.startswith("class "):
            _, ids, name = ln.split(None, 2)
            for i in ids.split(","):
                ir["classes"][i.strip()] = name.strip()
        elif ln.startswith("style "):
            _, target, rest = ln.split(None, 2)
            ir["styles"][target] = _props(rest)
        elif m := _EDGE.match(ln):
            a, op, label, b = m.groups()
            (ir["hints"] if op == "~~~" else ir["edges"]).append((a, b) if op == "~~~" else (a, op, label or "", b))
        elif m := _NODE.match(ln):
            ir["nodes"][m.group(1)] = {"label": m.group(2), "box": stack[-1]["id"] if stack else None}
            if stack:
                stack[-1]["nodes"].append(m.group(1))
    return ir


def _node_from_label(mid: str, label: str, ir: dict, meta: dict) -> dict:
    parts = label.replace("#quot;", '"').split("<br/>")
    n: dict = {"id": (meta.get("ids") or {}).get(mid, mid)}
    body = parts
    m = re.match(r"^<b>(.*?)</b>\s*(.*)$", parts[0])
    if m:
        n["name"] = m.group(1)
        if m.group(2):
            n["note"] = m.group(2)
        body = parts[1:]
    if body and _CMD.match(body[0]):
        n["cmd"] = re.findall(r"<code>([^<]*)</code>", body[0])
        body = body[1:]
    status = re.match(r"^<i>\[(\w+)\]</i>$", body[-1]) if body else None
    if status:
        n["status"] = status.group(1)
        body = body[:-1]
    if body:
        n["summary"] = [re.sub(r"<code>([^<]*)</code>", r"`\1`", s) for s in body]
    if mid in ir["classes"]:
        n["style"] = ir["classes"][mid]
    return n


def from_ir(ir: dict) -> dict:
    """Build the architecture dict from a parsed flowchart."""
    meta = ir["meta"]
    ids = meta.get("ids") or {}   # mermaid id -> architecture id, for the ids Mermaid cannot spell as written
    arch: dict = {"arch": 1}
    if meta.get("name"):
        arch["name"] = meta["name"]
    if meta.get("title"):
        arch["title"] = meta["title"]
    arch["layout"] = ir["layout"]
    if ir["direction"] != "TB":
        arch["direction"] = ir["direction"]
    used_styles = set(ir["classes"].values())
    if styles := {k: v for k, v in ir["classdefs"].items() if k in used_styles}:
        arch["styles"] = styles
    gnames = dict(meta.get("group_styles") or {})     # arch group id -> style name
    gstyles: dict[str, dict] = {}
    layers: list[dict] = []
    ranks_seen = []
    for pos, box in enumerate(ir["boxes"]):
        title = _unhtml_title(box["title"])
        m = _TITLE.match(title)
        rank = int(m.group(1)) if m else len(ir["boxes"]) - 1 - pos
        layer: dict = {"id": box["id"], "rank": rank, "title": m.group(2) if m else title}
        ranks_seen.append(rank)
        if box["direction"] and box["direction"] != ("LR" if box["nodes"] and not box["children"] else "none"):
            layer["direction"] = box["direction"]
        elif not box["direction"] and box["nodes"] and not box["children"]:
            layer["direction"] = "none"
        if box["nodes"]:
            layer["nodes"] = [_node_from_label(i, ir["nodes"][i]["label"], ir, meta) for i in box["nodes"]]
        if box["children"]:
            groups = []
            for g in box["children"]:
                grp: dict = {"id": g["id"], "title": _unhtml_title(g["title"])}
                if style := ir["styles"].get(g["id"]):
                    name = gnames.get(g["id"]) or next((k for k, v in gstyles.items() if v == style), f"group{len(gstyles) + 1}")
                    gstyles.setdefault(name, style)
                    grp["style"] = name
                grp["nodes"] = [_node_from_label(i, ir["nodes"][i]["label"], ir, meta) for i in g["nodes"]]
                groups.append(grp)
            layer["groups"] = _rows(groups, box["children"], ir)
        layers.append(layer)
    if gstyles:
        arch["group_styles"] = gstyles
    if meta.get("rules"):
        arch["rules"] = meta["rules"]
    for layer in layers:
        for n in _all_nodes(layer):
            n.update(meta.get("nodes", {}).get(n["id"], {}))
    network = {tuple(x) for x in meta.get("network", [])}
    edges = []
    for a, op, label, b in ir["edges"]:
        a, b = ids.get(a, a), ids.get(b, b)
        e: dict = {"from": a, "to": b}
        if op == "-.->":
            e["kind"] = "network" if (a, b) in network else "optional"
        if label:
            e["label"] = label
        edges.append(e)
    for h in sorted(meta.get("hidden") or [], key=lambda h: h["at"]):     # edges the picture leaves out come back at their place
        edges.insert(h["at"], h["edge"])
    arch["layers"] = layers
    arch["edges"] = edges
    return arch


def _all_nodes(layer: dict):
    yield from layer.get("nodes") or []
    for g in layer.get("groups") or []:
        yield from g.get("nodes") or []


def _rows(groups: list[dict], boxes: list[dict], ir: dict) -> list[dict]:
    """A group's row is read back from the invisible `a ~~~ b` links: b's group sits one row below a's."""
    owner = {nid: g["id"] for g in boxes for nid in g["nodes"]}
    row = {g["id"]: 1 for g in boxes}
    for _ in range(len(boxes)):
        for a, b in ir["hints"]:
            ga, gb = owner.get(a), owner.get(b)
            if ga and gb and ga != gb:
                row[gb] = max(row[gb], row[ga] + 1)
    if any(r > 1 for r in row.values()):
        for g in groups:
            g["row"] = row[g["id"]]
    return groups


def to_arch(text: str) -> dict:
    return from_ir(parse(text))


def convert(src: str | Path, out: str | Path | None = None) -> tuple[Path, list[str]]:
    """Read a `.mmd`, write the `.arch.yaml`. Returns (path, notes) where notes lists what was guessed for lack of arch-meta."""
    src = Path(src)
    text = src.read_text(encoding="utf-8")
    ir = parse(text)
    arch = from_ir(ir)
    notes = []
    if not ir["meta"]:
        notes.append("no `%% arch-meta:` line: package names, rules and edge kinds (network vs optional) are not recovered")
    if not all(_TITLE.match(_unhtml_title(b["title"])) for b in ir["boxes"]):
        notes.append("a layer title has no `N · ` rank prefix: ranks were assigned top-down")
    dest = Path(out) if out else src.with_suffix(".arch.yaml")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(arch, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    return dest, notes


# ---- the round trip -------------------------------------------------------------------------------------------------------------------

def normalize(arch: dict) -> dict:
    """The meaning of an architecture, with defaults filled in and unused styles dropped, so two files can be compared."""
    used = {n.get("style") for layer in arch.get("layers") or [] for n in _all_nodes(layer)} - {None}
    gused = {g.get("style") for layer in arch.get("layers") or [] for g in layer.get("groups") or []} - {None}
    layers = []
    for layer in arch.get("layers") or []:
        direction = layer.get("direction") or ("LR" if layer.get("nodes") and not layer.get("groups") else "none")
        layers.append({"id": layer["id"], "rank": layer.get("rank", 0), "title": _unhtml_title(layer.get("title", "")), "direction": direction,
                       "nodes": [_nn(n) for n in layer.get("nodes") or []],
                       "groups": [{"id": g["id"], "title": g["title"], "row": g.get("row", 1), "style": g.get("style"), "nodes": [_nn(n) for n in g.get("nodes") or []]}
                                  for g in layer.get("groups") or []]})
    return {"name": arch.get("name"), "title": arch.get("title"), "layout": arch.get("layout", "elk"), "direction": arch.get("direction", "TB"),
            "rules": arch.get("rules") or {},
            "styles": {k: v for k, v in (arch.get("styles") or {}).items() if k in used},
            "group_styles": {k: v for k, v in (arch.get("group_styles") or {}).items() if k in gused},
            "layers": layers,
            "edges": [{"from": e["from"], "to": e["to"], "kind": e.get("kind", "requires"), "label": e.get("label", ""), "draw": e.get("draw", True)} for e in arch.get("edges") or []]}


def _nn(n: dict) -> dict:
    return {"id": n["id"], "name": n.get("name"), "note": n.get("note"), "cmd": n.get("cmd") or [], "summary": n.get("summary") or [],
            "style": n.get("style"), "status": n.get("status"), "pkg": n.get("pkg"), "repo": n.get("repo"), "contract": n.get("contract") or {}}


def _diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            out += _diff(a.get(k), b.get(k), f"{path}.{k}" if path else str(k))
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def roundtrip_arch(arch: dict) -> list[str]:
    """arch -> mmd -> arch. Returns the differences (empty = the drawing lost nothing)."""
    errors, _ = validate(arch)
    if errors:
        raise ArchError("\n".join("  " + e for e in errors))
    return _diff(normalize(arch), normalize(to_arch(to_mermaid(arch))))


def _picture(text: str) -> dict:
    """What a flowchart shows, independent of how it is spelled: boxes, labels, edges, hints, classes (comments and spacing dropped)."""
    ir = parse(text)

    def tree(box):
        return {"id": box["id"], "title": _unhtml_title(box["title"]), "direction": box["direction"] or "none",
                "nodes": [(i, ir["nodes"][i]["label"].replace("#quot;", '"')) for i in box["nodes"]], "children": [tree(c) for c in box["children"]]}

    return {"layout": ir["layout"], "direction": ir["direction"], "boxes": [tree(b) for b in ir["boxes"]],
            "edges": sorted(ir["edges"]), "hints": sorted(ir["hints"]),
            "classes": {k: v for k, v in sorted(ir["classes"].items())},
            "classdefs": {k: v for k, v in sorted(ir["classdefs"].items()) if k in set(ir["classes"].values())},
            "styles": {k: v for k, v in sorted(ir["styles"].items())}}


def roundtrip_mmd(text: str) -> list[str]:
    """mmd -> arch -> mmd. Returns the differences between the two pictures (empty = reading the picture lost nothing)."""
    arch = to_arch(text)
    return _diff(_picture(text), _picture(to_mermaid(arch)))
