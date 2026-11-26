"""`graf util arch2mmd`: an `.arch.yaml` architecture graph -> a Mermaid `.mmd` flowchart.

The architecture is the source of truth and the picture is generated from it. Before it draws, `validate()` checks the graph
against the rules the file declares (edges never point up the layers, `requires` edges have no cycle), so a drawing never
shows an architecture that breaks its own constraints. No LLM, no dependency beyond PyYAML.

Schema (arch: 1): see the header of examples such as `digital-duck.arch.yaml`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

KINDS = ("requires", "optional", "network")
STATUSES = ("planned", "prototype", "validated", "product")
CONTRACT_KEYS = ("tests", "files", "guarantees")   # tests/files: paths under the node's repo that must exist; guarantees: what the node promises
_ARROW = {"requires": "-->", "optional": "-.->", "network": "-.->"}


class ArchError(Exception):
    """The architecture file is malformed or breaks its own rules."""


def load(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("arch") != 1:
        raise ArchError("not an architecture file: the top level must be a mapping with `arch: 1`")
    return data


def _nodes(arch: dict):
    """Yield (node, layer, group-or-None) in file order."""
    for layer in arch.get("layers") or []:
        for n in layer.get("nodes") or []:
            yield n, layer, None
        for g in layer.get("groups") or []:
            for n in g.get("nodes") or []:
                yield n, layer, g


def validate(arch: dict) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors stop the drawing; warnings do not."""
    errors: list[str] = []
    warnings: list[str] = []
    styles, gstyles = arch.get("styles") or {}, arch.get("group_styles") or {}
    rank: dict[str, int] = {}
    seen: set[str] = set()
    for n, layer, _ in _nodes(arch):
        nid = n.get("id")
        if not nid:
            errors.append(f"a node in layer {layer.get('id')!r} has no id")
            continue
        if nid in seen:
            errors.append(f"duplicate node id {nid!r}")
        seen.add(nid)
        rank[nid] = layer.get("rank", 0)
        if n.get("style") and n["style"] not in styles:
            errors.append(f"node {nid!r}: unknown style {n['style']!r}")
        if n.get("status", "product") not in STATUSES:
            errors.append(f"node {nid!r}: status must be one of {', '.join(STATUSES)}")
        c = n.get("contract")
        if c is not None:
            if not isinstance(c, dict):
                errors.append(f"node {nid!r}: contract must be a mapping")
            else:
                for k, v in c.items():
                    if k not in CONTRACT_KEYS:
                        errors.append(f"node {nid!r}: unknown contract key {k!r} (allowed: {', '.join(CONTRACT_KEYS)})")
                    elif not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                        errors.append(f"node {nid!r}: contract.{k} must be a list of strings")
        if not (n.get("name") or n.get("summary")):
            errors.append(f"node {nid!r} has neither a name nor a summary")
    mids: dict[str, str] = {}
    boxes = [n["id"] for n, _l, _g in _nodes(arch) if n.get("id")]
    boxes += [l["id"] for l in arch.get("layers") or []] + [g["id"] for l in arch.get("layers") or [] for g in l.get("groups") or []]
    for bid in boxes:
        m = _mid(bid)
        if m in mids and mids[m] != bid:
            errors.append(f"id {bid!r} collides with {mids[m]!r} once drawn (nodes, layers and groups share one namespace)")
        mids.setdefault(m, bid)
    for layer in arch.get("layers") or []:
        for g in layer.get("groups") or []:
            if g.get("style") and g["style"] not in gstyles:
                errors.append(f"group {g.get('id')!r}: unknown group style {g['style']!r}")
    rules = arch.get("rules") or {}
    requires: dict[str, list[str]] = {}
    for e in arch.get("edges") or []:
        a, b, kind = e.get("from"), e.get("to"), e.get("kind", "requires")
        if a not in rank or b not in rank:
            errors.append(f"edge {a} -> {b}: unknown node {a if a not in rank else b!r}")
            continue
        if kind not in KINDS:
            errors.append(f"edge {a} -> {b}: kind must be one of {', '.join(KINDS)}")
        if rules.get("edges_point_down") and rank[a] < rank[b]:
            errors.append(f"edge {a} -> {b} points up (rank {rank[a]} -> {rank[b]}), which the architecture's rules forbid")
        if kind == "requires":
            requires.setdefault(a, []).append(b)
    if rules.get("requires_acyclic"):
        state: dict[str, int] = {}

        def visit(u: str, stack: list[str]) -> None:
            state[u] = 1
            for v in requires.get(u, []):
                if state.get(v) == 1:
                    path = stack + [u]
                    errors.append("`requires` cycle: " + " -> ".join(path[path.index(v):] + [v]))
                elif v not in state:
                    visit(v, stack + [u])
            state[u] = 2

        for u in list(requires):
            if u not in state:
                visit(u, [])
    linked = {e.get("from") for e in arch.get("edges") or []} | {e.get("to") for e in arch.get("edges") or []}
    for nid in rank:
        if nid not in linked:
            warnings.append(f"node {nid!r} has no edges")
    return errors, warnings


_RESERVED = {"end", "graph", "subgraph", "flowchart", "style", "class", "classdef", "click", "default", "direction", "linkstyle", "interpolate"}


def _mid(nid: str) -> str:
    """The Mermaid id of an architecture id: itself when Mermaid accepts it, else `n_` + a sanitized form."""
    if re.fullmatch(r"[A-Za-z]\w*", nid) and nid.lower() not in _RESERVED:
        return nid
    return "n_" + re.sub(r"\W", "_", nid)


def _esc(text: str) -> str:
    return str(text).replace('"', "#quot;")


def _inline(text: str) -> str:
    """`code` -> <code>code</code>; the rest is kept (so &nbsp; and similar entities pass through)."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", _esc(text))


def _label(n: dict) -> str:
    parts = []
    if n.get("name"):
        head = f"<b>{_esc(n['name'])}</b>"
        if n.get("note"):
            head += f" {_esc(n['note'])}"
        parts.append(head)
    if n.get("cmd"):
        parts.append(" / ".join(f"<code>{_esc(c)}</code>" for c in n["cmd"]))
    parts += [_inline(s) for s in n.get("summary") or []]
    if n.get("status") in ("planned", "prototype"):      # only the not-yet-validated ones are drawn; validated and product are the unmarked norm
        parts.append(f"<i>[{n['status']}]</i>")
    return "<br/>".join(parts)


def _style_line(kw: str, target: str, d: dict) -> str:
    return f"    {kw} {target} " + ",".join(f"{k}:{v}" for k, v in d.items())


def _title(layer: dict) -> str:
    return _esc(f"{layer.get('rank', 0)} · {layer['title']}").replace(" ", "&nbsp;") if layer.get("title") else " "


def to_mermaid(arch: dict, source: str = "") -> str:
    """The Mermaid flowchart for a validated architecture."""
    out = ["---", "config:", f"  layout: {arch.get('layout', 'elk')}", "---", f"flowchart {arch.get('direction', 'TB')}"]
    out.append(f"    %% generated by `graf util arch2mmd` from {source or 'an .arch.yaml'}: edit that file, not this one")
    classes: dict[str, list[str]] = {}
    group_style_of: dict[str, str] = {}
    group_style_ids: dict[str, str] = {}
    rows_by_layer: dict[str, dict[int, list[dict]]] = {}

    def emit_node(n: dict, ind: str) -> None:
        out.append(f'{ind}{_mid(n["id"])}["{_label(n)}"]')
        if n.get("style"):
            classes.setdefault(n["style"], []).append(_mid(n["id"]))

    for layer in arch.get("layers") or []:
        lid = _mid(layer["id"])
        out.append(f"\n    %% ───────────── layer {layer.get('rank', 0)}: {layer.get('title', layer['id'])} ─────────────")
        out.append(f'    subgraph {lid}["{_title(layer)}"]')
        direction = layer.get("direction") or ("LR" if layer.get("nodes") and not layer.get("groups") else "none")
        if direction != "none":
            out.append(f"        direction {direction}")
        for n in layer.get("nodes") or []:
            emit_node(n, "        ")
        for g in layer.get("groups") or []:
            gid = _mid(g["id"])
            out.append(f'        subgraph {gid}["{_esc(g["title"]).replace(" ", "&nbsp;")}"]')
            for n in g.get("nodes") or []:
                emit_node(n, "            ")
            out.append("        end")
            if g.get("style"):
                group_style_of[gid] = g["style"]
                group_style_ids[gid] = g["id"]
            rows_by_layer.setdefault(layer["id"], {}).setdefault(g.get("row", 1), []).append(g)
        out.append("    end")

    out.append("")
    hidden = []
    for i, e in enumerate(arch.get("edges") or []):
        if e.get("draw") is False:      # part of the graph, left out of the picture (e.g. so two boxes can share a row)
            hidden.append({"at": i, "edge": e})
            continue
        arrow = _ARROW[e.get("kind", "requires")]
        label = f'|"{_esc(e["label"])}"|' if e.get("label") else ""
        out.append(f"    {_mid(e['from'])} {arrow}{label} {_mid(e['to'])}")

    hints = []
    for rows in rows_by_layer.values():
        order = sorted(rows)
        for r0, r1 in zip(order, order[1:]):
            for g0, g1 in zip(rows[r0], rows[r1]):  # i-th group of a row sits above the i-th group of the next row
                for a, b in zip(g0.get("nodes") or [], g1.get("nodes") or []):
                    hints.append(f"    {_mid(a['id'])} ~~~ {_mid(b['id'])}")
    if hints:
        out += ["", "    %% invisible links: stack the rows of groups inside a layer"] + hints

    meta: dict = {k: arch[k] for k in ("name", "title", "rules") if arch.get(k)}
    nodes_meta = {n["id"]: {k: n[k] for k in ("pkg", "repo", "contract", "status") if n.get(k)} for n, _l, _g in _nodes(arch)
                  if any(n.get(k) for k in ("pkg", "repo", "contract", "status"))}
    if nodes_meta:
        meta["nodes"] = nodes_meta
    if group_style_of:
        meta["group_styles"] = {group_style_ids[g]: n for g, n in group_style_of.items()}
    ids = {_mid(n["id"]): n["id"] for n, _l, _g in _nodes(arch) if _mid(n["id"]) != n["id"]}   # ids Mermaid cannot spell as written
    if ids:
        meta["ids"] = ids
    network = [[e["from"], e["to"]] for e in arch.get("edges") or [] if e.get("kind") == "network"]
    if network:
        meta["network"] = network
    if hidden:
        meta["hidden"] = hidden
    out.append("")
    for name, d in (arch.get("styles") or {}).items():
        if name in classes:
            out.append(_style_line("classDef", name, d))
    gstyles = arch.get("group_styles") or {}
    for gid, name in group_style_of.items():
        out.append(_style_line("style", gid, gstyles[name]))
    out.append("")
    for name, ids in classes.items():
        out.append(f"    class {','.join(ids)} {name}")
    if meta:   # what the picture cannot show; `graf util mmd2arch` reads it back so the round trip is lossless
        out += ["", "    %% arch-meta: " + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))]
    return "\n".join(out) + "\n"


def convert(src: str | Path, out: str | Path | None = None, *, strict: bool = False) -> tuple[Path, list[str]]:
    """Read `src`, validate it, write the `.mmd`. Returns (path, warnings). Raises ArchError on errors (or warnings, if strict)."""
    src = Path(src)
    arch = load(src)
    errors, warnings = validate(arch)
    if errors or (strict and warnings):
        raise ArchError("\n".join(["  " + m for m in errors + (warnings if strict else [])]))
    dest = Path(out) if out else src.with_name(src.name.removesuffix(".arch.yaml").removesuffix(".yaml") + ".mmd")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(to_mermaid(arch, src.name), encoding="utf-8")
    return dest, warnings
