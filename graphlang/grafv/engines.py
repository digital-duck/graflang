"""Draw a workflow graph (see `model.build`). Engines (`graf vis --engine NAME`):

  cytoscape  one self-contained HTML file; Cytoscape.js is bundled, so it works offline. Default.
  graphviz   static SVG through the `dot` program (DOT text is written if `dot` is not installed).
  pyvis      interactive HTML via the pyvis package (`pip install 'graflang[vis]'`); left-to-right, no physics.
  graphify   graphify's community-coloured HTML export (`pip install 'graflang[graphify]'`); undirected, so no edge types.
  mermaid    Mermaid flowchart text (`.mmd`, or a fenced block when `-o` ends in `.md`): paste into GitHub, mkdocs or mermaid.live.

All but graphify draw control edges (`triggers`) solid and data edges (`binds`) dashed, and a LOOP as a box around its body.
"""
from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import networkx as nx

from .model import OTHER_COLOR, TYPE_COLORS, build

DEFAULT_ENGINE = "cytoscape"
CONTROL_COLOR, DATA_COLOR = "#6b7280", "#4f8ef7"
SHAPES = {"INPUT": "round-rectangle", "OUTPUT": "round-rectangle", "EMIT": "round-rectangle",
          "EVALUATE": "diamond", "ASSERT": "diamond", "GUARD": "diamond", "FORK": "hexagon", "JOIN": "hexagon"}

# ---- cytoscape -------------------------------------------------------------------------------------------------

CYTOSCAPE_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;font:16px system-ui,sans-serif;background:#fff;color:#222}
  #bar{display:flex;gap:12px;align-items:center;padding:8px 12px;min-height:34px;border-bottom:1px solid #ddd;flex-wrap:wrap}
  #cy{position:absolute;top:52px;bottom:0;left:0;right:340px}
  #side{position:absolute;top:52px;bottom:0;right:0;width:340px;font-size:15px;overflow:auto;border-left:1px solid #ddd;padding:8px;box-sizing:border-box}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 3px 0 8px}
  .ln{display:inline-block;width:22px;border-top:2px solid #6b7280;vertical-align:middle;margin:0 3px 0 8px}
  .ln.d{border-top-style:dashed;border-color:#4f8ef7}
  button{font-size:15px;min-width:34px;padding:2px 8px;cursor:pointer}
  pre{white-space:pre-wrap;word-break:break-word;margin:4px 0}
  @media (prefers-color-scheme: dark){html,body{background:#16181d;color:#e6e6e6}#bar,#side{border-color:#333}input,select{font-size:15px;background:#222;color:#eee;border:1px solid #444}}
</style></head><body>
<div id="bar"><b>__TITLE__</b><input id="q" placeholder="find a node" size="18" style="font-size:15px">
 <select id="layout" style="font-size:15px">__LAYOUTS__</select>
 <button id="zin" title="Zoom in">+</button><button id="zout" title="Zoom out">&minus;</button><button id="zfit" title="Fit the whole graph">Fit</button><button id="reset" title="Clear the selection, the highlight and the search">Reset</button>
 <span>__LEGEND__</span><span style="opacity:.7">__NOTE__</span></div>
<div id="cy"></div><div id="side"><i>Click a node.</i></div>
<script>__CYTOSCAPE__</script>
<script>
const data = __DATA__;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const cy = cytoscape({container: document.getElementById('cy'), elements: data, layout: {name: 'preset'}, wheelSensitivity: 0.08, minZoom: 0.05, maxZoom: 4,
  style: [
    {selector:'node', style:{'background-color':'data(color)', 'background-opacity':0.85, shape:'data(shape)', label:'data(text)',
      'text-wrap':'wrap', 'font-size':13, 'min-zoomed-font-size':5, width:130, height:48, color:'#111',
      'text-valign':'center', 'text-halign':'center', 'border-width':1, 'border-color':'data(color)'}},
    {selector:'node[shape="diamond"]', style:{width:150, height:70}},
    {selector:':parent', style:{'background-opacity':0.07, 'border-style':'dashed', 'border-width':2, 'text-valign':'top',
      'text-halign':'center', 'padding':20, shape:'round-rectangle', color: dark?'#ddd':'#333', 'font-weight':'bold'}},
    {selector:'edge', style:{width:2, 'line-color':'#6b7280', 'target-arrow-color':'#6b7280', 'target-arrow-shape':'triangle',
      'curve-style':'bezier', label:'data(label)', 'font-size':11, color: dark?'#bbb':'#555',
      'text-background-color': dark?'#16181d':'#fff', 'text-background-opacity':0.9, 'text-background-padding':2}},
    {selector:'edge[relation="binds"]', style:{'line-style':'dashed', width:1.5, 'line-color':'#4f8ef7', 'target-arrow-color':'#4f8ef7'}},
    {selector:'.faded', style:{opacity:0.12}},
    {selector:'node:selected', style:{'border-width':4, 'border-color':'#e5484d'}}]});
function layout(){
  const name = document.getElementById('layout').value === 'dot' ? 'preset' : document.getElementById('layout').value;
  const l = cy.layout({name, animate:false, padding:30, directed:true, spacingFactor:1.25, nodeRepulsion: 9000,
                       nodeDimensionsIncludeLabels:true, fit:true});
  l.on('layoutstop', () => cy.fit(undefined, 30));
  l.run(); cy.fit(undefined, 30);
}
layout();
window.addEventListener('resize', () => cy.fit(undefined, 30));
document.getElementById('layout').onchange = layout;
function zoomBy(f){ cy.zoom({level: cy.zoom() * f, renderedPosition: {x: cy.width() / 2, y: cy.height() / 2}}); }
document.getElementById('zin').onclick = () => zoomBy(1.3);
document.getElementById('zout').onclick = () => zoomBy(1 / 1.3);
document.getElementById('zfit').onclick = () => cy.fit(undefined, 30);
document.getElementById('reset').onclick = () => {
  cy.elements().unselect().removeClass('faded');
  document.getElementById('q').value = '';
  document.getElementById('side').innerHTML = '<i>Click a node.</i>';
};
cy.on('tap','node', e => {
  const n = e.target, nb = n.closedNeighborhood();
  cy.elements().addClass('faded'); nb.removeClass('faded');
  const d = n.data(), esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const other = x => (x.source().id()===n.id() ? x.target() : x.source()).data('label');
  const rows = n.connectedEdges().map(x => (x.source().id()===n.id() ? '→ ' : '← ') + esc(x.data('relation')) + ' ' +
    esc(other(x)) + '  (' + esc(x.data('sport')) + ' → ' + esc(x.data('tport')) + ')').sort();
  document.getElementById('side').innerHTML = '<b>' + esc(d.label) + '</b><pre>' + esc(d.info) + '</pre><b>Links</b><pre>' + rows.join('\\n') + '</pre>';
});
cy.on('tap', e => { if (e.target === cy) { cy.elements().removeClass('faded'); } });
document.getElementById('q').oninput = e => {
  const t = e.target.value.toLowerCase(); cy.elements().removeClass('faded');
  if (!t) return;
  const hit = cy.nodes().filter(n => n.data('label').toLowerCase().includes(t));
  cy.elements().not(hit).addClass('faded'); if (hit.length) cy.fit(hit, 60);
};
</script></body></html>
"""


def _legend(G: nx.MultiDiGraph) -> str:
    kinds = sorted({d["kind"] for _, d in G.nodes(data=True)})
    boxes = "".join(f'<span class="sw" style="background:{TYPE_COLORS.get(k, OTHER_COLOR)}"></span>{html.escape(k)}' for k in kinds)
    return boxes + '<span class="ln"></span>control<span class="ln d"></span>data'


def cytoscape_html(G: nx.MultiDiGraph, note: str = "") -> str:
    """The self-contained page for G. Node positions come from `dot` when it is installed (it lays out clusters properly)."""
    pos = dot_positions(G)
    layouts = (["dot"] if pos else []) + ["cose", "breadthfirst", "concentric", "circle", "grid"]
    elements = [{**({"position": pos[n]} if n in pos else {}), "data": {"id": n, "label": d["label"], "text": d["label"] if G.nodes[n].get("kind") == "LOOP"
                          else f'{d["label"]}\n{d["kind"]}', "color": d["color"], "info": d["info"],
                          "shape": SHAPES.get(d["kind"], "rectangle"), **({"parent": d["parent"]} if d.get("parent") else {})}}
                for n, d in G.nodes(data=True)]
    elements += [{"data": {"id": f"e{i}", "source": u, "target": v, "relation": d["relation"], "label": d["label"],
                           "sport": d["sport"], "tport": d["tport"]}}
                 for i, (u, v, d) in enumerate(G.edges(data=True))]
    js = (resources.files("graphlang.grafv") / "data" / "cytoscape.min.js").read_text(encoding="utf-8")
    title = f'{G.graph.get("name", "workflow")} (GraphLang)'
    return (CYTOSCAPE_PAGE.replace("__TITLE__", html.escape(title)).replace("__NOTE__", html.escape(note))
            .replace("__LEGEND__", _legend(G))
            .replace("__LAYOUTS__", "".join(f"<option>{l}</option>" for l in layouts))
            .replace("__DATA__", json.dumps(elements).replace("</", "<\\/"))
            .replace("__CYTOSCAPE__", js.replace("</script", "<\\/script")))


def to_cytoscape(G: nx.MultiDiGraph, out: Path, note: str = "") -> None:
    out.write_text(cytoscape_html(G, note), encoding="utf-8")


# ---- graphviz --------------------------------------------------------------------------------------------------

def graphviz_ready() -> Tuple[bool, str]:
    return (True, "dot found") if shutil.which("dot") else (False, "dot not found (install graphviz); DOT text is written instead")


_DOT_SHAPES = {"round-rectangle": "box", "diamond": "diamond", "hexagon": "hexagon", "rectangle": "box"}


def to_dot(G: nx.MultiDiGraph, fixed_size: bool = False) -> str:
    """DOT text: LOOP bodies become clusters; the LOOP node itself sits inside its cluster as the anchor for outer edges.
    `fixed_size` gives every node the size it has on the interactive page, so positions computed here fit there."""
    esc = lambda s: str(s).replace("\\", "/").replace('"', "'")  # noqa: E731

    def node_line(n: str, pad: str) -> str:
        d = G.nodes[n]
        shape = _DOT_SHAPES[SHAPES.get(d["kind"], "rectangle")]
        style = "rounded,filled" if shape == "box" else "filled"
        size = ""
        if fixed_size:
            w, h = (150, 70) if shape == "diamond" else (130, 48)
            size = f", fixedsize=true, width={w / 72:.3f}, height={h / 72:.3f}"
        return (f'{pad}"{esc(n)}" [label="{esc(d["label"])}\\n{d["kind"]}", shape={shape}, style="{style}", '
                f'fillcolor="{d["color"]}55", color="{d["color"]}"{size}];')

    def emit(parent, pad: str) -> list:
        lines = []
        for n in [n for n in G if G.nodes[n].get("parent") == parent]:
            children = [c for c in G if G.nodes[c].get("parent") == n]
            if children:
                lines += [f'{pad}subgraph "cluster_{esc(n)}" {{', f'{pad}  label="{esc(G.nodes[n]["label"])}"; style="dashed,rounded"; '
                          f'color="{G.nodes[n]["color"]}";', node_line(n, pad + "  ")]
                lines += emit(n, pad + "  ")
                lines.append(f"{pad}}}")
            else:
                lines.append(node_line(n, pad))
        return lines

    lines = ["digraph G {", "  rankdir=LR; compound=true; fontsize=11;", '  node [fontsize=11, fontcolor="#222"];']
    lines += emit(None, "  ")
    for u, v, d in G.edges(data=True):
        data = d["relation"] == "binds"
        attrs = [f'label="{esc(d["label"])}"', "fontsize=9", f'color="{DATA_COLOR if data else CONTROL_COLOR}"',
                 f'fontcolor="{DATA_COLOR if data else CONTROL_COLOR}"']
        if data:
            attrs += ["style=dashed", "constraint=false"]
        lines.append(f'  "{esc(u)}" -> "{esc(v)}" [{", ".join(attrs)}];')
    return "\n".join(lines + ["}"])


def dot_positions(G: nx.MultiDiGraph, canvas_aspect: float = 1.6) -> Dict[str, Dict[str, float]]:
    """Node centres (cytoscape pixels, y down) from `dot -Tjson`; {} when `dot` is missing or fails.
    Lays the graph out left-to-right and top-to-bottom and keeps the one whose shape is closer to the page's
    (a long pipeline is unreadable as one very wide row). A LOOP is a box on the page, so its own (anchor)
    position is left out and the box wraps its body."""
    if not shutil.which("dot"):
        return {}
    loops = {n for n in G if any(G.nodes[c].get("parent") == n for c in G)}
    best, best_score = {}, None
    for rankdir in ("LR", "TB"):
        text = to_dot(G, fixed_size=True).replace("rankdir=LR;", f"rankdir={rankdir}; nodesep=0.5; ranksep=0.9;")
        r = subprocess.run(["dot", "-Tjson"], input=text, text=True, capture_output=True)
        if r.returncode:
            continue
        try:
            j = json.loads(r.stdout)
            _, _, w, h = (float(v) for v in j["bb"].split(","))
            pos = {o["name"]: {"x": float(o["pos"].split(",")[0]), "y": -float(o["pos"].split(",")[1])}
                   for o in j.get("objects", []) if o.get("name") in G and o["name"] not in loops and "pos" in o}
        except (ValueError, KeyError):
            continue
        score = abs(math.log((w / max(h, 1.0)) / canvas_aspect))
        if best_score is None or score < best_score:
            best, best_score = pos, score
    return best


def to_graphviz(G: nx.MultiDiGraph, out: Path, note: str = "") -> None:
    dot = to_dot(G)
    if shutil.which("dot"):
        r = subprocess.run(["dot", "-Tsvg", "-o", str(out)], input=dot, text=True, capture_output=True)
        if r.returncode:
            raise RuntimeError(f"dot failed: {r.stderr.strip()[:200]}")
    else:
        out.with_suffix(".dot").write_text(dot, encoding="utf-8")
        raise RuntimeError(f"dot is not installed; wrote DOT text to {out.with_suffix('.dot')}")


# ---- pyvis -----------------------------------------------------------------------------------------------------

def pyvis_ready() -> Tuple[bool, str]:
    try:
        import pyvis  # noqa: F401
        return True, "pyvis installed"
    except ImportError:
        return False, "needs pyvis: pip install 'graflang[vis]'"


PYVIS_OPTIONS = json.dumps({
    "layout": {"hierarchical": {"enabled": True, "direction": "LR", "sortMethod": "directed", "levelSeparation": 200,
                                "nodeSpacing": 120}},
    "physics": {"enabled": False},
    "edges": {"smooth": {"type": "cubicBezier"}, "font": {"size": 11, "align": "middle"}},
})


def to_pyvis(G: nx.MultiDiGraph, out: Path, note: str = "") -> None:
    from pyvis.network import Network
    net = Network(height="100vh", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    for n, d in G.nodes(data=True):
        shape = {"diamond": "diamond", "hexagon": "hexagon"}.get(SHAPES.get(d["kind"], "rectangle"), "box")
        in_loop = d.get("parent")
        net.add_node(n, label=f'{d["label"]}\n{d["kind"]}', title=d["info"] + (f"\nin loop: {in_loop}" if in_loop else ""),
                     color={"background": d["color"], "border": d["color"]}, shape=shape, borderWidth=3 if d["kind"] == "LOOP" else 1,
                     shapeProperties={"borderDashes": [5, 5]} if in_loop else {})
    for u, v, d in G.edges(data=True):
        data = d["relation"] == "binds"
        net.add_edge(u, v, label=d["label"], title=f'{d["relation"]}: {d["sport"]} -> {d["tport"]}', arrows="to",
                     dashes=data, color=DATA_COLOR if data else CONTROL_COLOR)
    net.set_options(PYVIS_OPTIONS)
    net.write_html(str(out), notebook=False)


# ---- graphify --------------------------------------------------------------------------------------------------

def graphify_ready() -> Tuple[bool, str]:
    try:
        import graphify.export  # noqa: F401
        return True, "graphify installed"
    except ImportError:
        return False, "needs graphify: pip install 'graflang[graphify]'"


def to_graphify(G: nx.MultiDiGraph, out: Path, note: str = "") -> None:
    from graphify.cluster import cluster
    from graphify.export import to_html
    U = nx.Graph()                                     # graphify wants an undirected graph and communities
    for n, d in G.nodes(data=True):
        U.add_node(n, label=d["label"], kind=d["kind"], source_file=d["info"])
    for u, v, d in G.edges(data=True):
        U.add_edge(u, v, relation=d["relation"], confidence="EXTRACTED" if d["relation"] == "triggers" else "INFERRED")
    communities = cluster(U) if U.number_of_nodes() else {}
    if not to_html(U, communities, str(out)):
        raise RuntimeError("graphify declined to export this graph")


# ---- mermaid ---------------------------------------------------------------------------------------------------

_MERMAID_SHAPES = {"round-rectangle": ("([", "])"), "diamond": ("{", "}"), "hexagon": ("{{", "}}"), "rectangle": ("[", "]")}


def to_mermaid_text(G: nx.MultiDiGraph) -> str:
    """A Mermaid flowchart: a LOOP is a `subgraph` around its body (edges to the loop point at the box)."""
    ids = {n: f"n{i}" for i, n in enumerate(G)}
    q = lambda s: str(s).replace('"', "#quot;")  # noqa: E731
    loops = {n for n in G if any(G.nodes[c].get("parent") == n for c in G)}
    lines = ["flowchart LR"]

    def emit(parent, pad: str) -> None:
        for n in [n for n in G if G.nodes[n].get("parent") == parent]:
            d = G.nodes[n]
            if n in loops:
                lines.append(f'{pad}subgraph {ids[n]}["{q(d["label"])} (LOOP)"]')
                emit(n, pad + "  ")
                lines.append(f"{pad}end")
            else:
                left, right = _MERMAID_SHAPES[SHAPES.get(d["kind"], "rectangle")]
                lines.append(f'{pad}{ids[n]}{left}"{q(d["label"])}<br/>{d["kind"]}"{right}')

    emit(None, "  ")
    for u, v, d in G.edges(data=True):
        arrow = "-.->" if d["relation"] == "binds" else "-->"
        label = f'|"{q(d["label"])}"|' if d["label"] else ""
        lines.append(f"  {ids[u]} {arrow}{label} {ids[v]}")
    for kind in sorted({d["kind"] for n, d in G.nodes(data=True) if n not in loops}):
        c = TYPE_COLORS.get(kind, OTHER_COLOR)
        members = ",".join(ids[n] for n, d in G.nodes(data=True) if d["kind"] == kind and n not in loops)
        lines += [f"  classDef {kind} fill:{c}55,stroke:{c},color:#222;", f"  class {members} {kind};"]
    return "\n".join(lines) + "\n"


def to_mermaid(G: nx.MultiDiGraph, out: Path, note: str = "") -> None:
    text = to_mermaid_text(G)
    out.write_text(f"```mermaid\n{text}```\n" if out.suffix == ".md" else text, encoding="utf-8")


# ---- registry --------------------------------------------------------------------------------------------------

ENGINES: Dict[str, Dict[str, Any]] = {
    "cytoscape": {"fn": to_cytoscape, "ext": ".html", "ready": lambda: (True, "bundled, works offline"),
                  "about": "interactive HTML (search, zoom, click a node for its config and links); no extra install"},
    "graphviz": {"fn": to_graphviz, "ext": ".svg", "ready": graphviz_ready, "about": "static SVG through `dot`; good for docs"},
    "pyvis": {"fn": to_pyvis, "ext": ".html", "ready": pyvis_ready, "required": True,
              "about": "interactive HTML via pyvis, left-to-right (pip install 'graflang[vis]')"},
    "graphify": {"fn": to_graphify, "ext": ".html", "ready": graphify_ready, "required": True,
                 "about": "graphify's HTML export coloured by community; undirected (pip install 'graflang[graphify]')"},
    "mermaid": {"fn": to_mermaid, "ext": ".mmd", "ready": lambda: (True, "plain text"), "open": False,
                "about": "Mermaid flowchart text for GitHub / docs / mermaid.live; -o FILE.md wraps it in a fenced block"},
}


def render(graph_data: Dict[str, Any], out: str | Path, engine: str = DEFAULT_ENGINE) -> Tuple[Path, str, int]:
    """Draw the workflow with `engine` into `out`. Returns (file, note, node count)."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}; choose from {sorted(ENGINES)}")
    G, note = build(graph_data)
    if not G.number_of_nodes():
        raise ValueError("nothing to draw: the workflow has no nodes")
    spec = ENGINES[engine]
    ok, why = spec["ready"]()
    if not ok and spec.get("required"):
        raise RuntimeError(why)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    spec["fn"](G, target, note)
    return target, note, G.number_of_nodes()
