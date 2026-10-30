"""`graf vis`: the workflow model, the cytoscape and graphviz engines, and the CLI."""
import json
import re
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafv import engines
from graphlang.grafv.model import build

ROOT = Path(__file__).resolve().parent.parent
COOKBOOK = ROOT / "cookbook"
CONCEPT_BOOK = COOKBOOK / "concept_book" / "build_concept_book.graph.yaml"
SELF_REFINE = COOKBOOK / "self_refine" / "self_refine.graph.yaml"


def workflow():
    """in -> a -> loop[b -> c, with a binds edge and a bad edge] -> out."""
    node = lambda i, t, ports, **cfg: {"id": i, "type": t, "ports": ports, **({"config": cfg} if cfg else {})}  # noqa: E731
    return {
        "workflow": {"name": "w"},
        "nodes": [
            node("start", "INPUT", ["entry", "out_x"]),
            node("a", "GENERATE", ["trigger", "complete", "in_x", "out_y"], prompt_ref="prompts.p", model="m"),
            node("lp", "LOOP", ["trigger", "exit"], condition="@cycle < 2", subgraph={
                "nodes": [node("b", "GENERATE", ["trigger", "complete", "out_z"]), node("c", "EVALUATE", ["trigger", "pass", "fail", "in_z"])],
                "edges": [{"source": "b.complete", "target": "c.trigger", "type": "triggers"},
                          {"source": "b.out_z", "target": "c.in_z", "type": "binds"},
                          {"source": "b.complete", "target": "ghost.trigger", "type": "triggers"}]}),
            node("end", "OUTPUT", ["trigger", "exit"]),
        ],
        "edges": [{"source": "start.entry", "target": "a.trigger", "type": "triggers"},
                  {"source": "start.out_x", "target": "a.in_x", "type": "binds"},
                  {"source": "a.complete", "target": "lp.trigger", "type": "triggers"},
                  {"source": "lp.exit", "target": "end.trigger", "type": "triggers"}],
    }


def test_model_nests_loop_bodies_and_labels_edges():
    G, note = build(workflow())
    assert set(G) == {"start", "a", "lp", "end", "lp/b", "lp/c"}
    assert G.nodes["lp/b"]["parent"] == "lp" and "parent" not in G.nodes["lp"]
    assert G.nodes["a"]["kind"] == "GENERATE" and "prompt_ref: prompts.p" in G.nodes["a"]["info"]
    edges = {(u, v, d["relation"]): d["label"] for u, v, d in G.edges(data=True)}
    assert edges[("start", "a", "binds")] == "x"            # data edges are labelled with the port, minus out_
    assert edges[("start", "a", "triggers")] == ""          # the default control port is not worth a label
    assert edges[("lp", "end", "triggers")] == "exit"
    assert edges[("lp/b", "lp/c", "binds")] == "z"
    assert "ghost.trigger" in note                          # an edge to an unknown node is skipped, and said so


def test_cookbook_graphs_all_build():
    from graphlang.grafr.runtime import load_graph
    for path in COOKBOOK.glob("*/*.graph.yaml"):
        G, note = build(load_graph(path))
        assert G.number_of_nodes() >= 3 and note == "", path


def _page_data(page):
    return json.loads(re.search(r"const data = (\[.*?\]);\nconst OPTS", page, re.S).group(1).replace("<\\/", "</"))


def test_cytoscape_page_is_self_contained_and_complete(tmp_path):
    out, note, n = engines.render(workflow(), tmp_path / "w.html")
    page = out.read_text(encoding="utf-8")
    assert n == 6 and "cytoscape(" in page and 'src="http' not in page and "https://" not in page.split("<script>")[0]
    data = _page_data(page)
    nodes = {e["data"]["id"]: e for e in data if "source" not in e["data"]}
    assert nodes["lp/b"]["data"]["parent"] == "lp" and nodes["lp/c"]["data"]["shape"] == "diamond"
    assert nodes["lp"]["data"]["text"] == "repeat while cycle < 2" and nodes["a"]["data"]["text"] == "p"     # labels say what a node does; the type line is off
    assert {e["data"]["relation"] for e in data if "source" in e["data"]} == {"triggers", "binds"}
    assert "GENERATE" in page and "control" in page and "data" in page          # legend


def test_cytoscape_uses_dot_positions_when_available_and_falls_back_without(tmp_path, monkeypatch):
    if shutil.which("dot"):
        data = _page_data(engines.render(workflow(), tmp_path / "a.html")[0].read_text(encoding="utf-8"))
        placed = {e["data"]["id"] for e in data if "position" in e}
        assert placed == {"start", "a", "end", "lp/b", "lp/c"}           # the LOOP is a box around its body: no position of its own
        assert "<option>dot</option>" in (tmp_path / "a.html").read_text(encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    out = engines.render(workflow(), tmp_path / "b.html")[0]
    page = out.read_text(encoding="utf-8")
    assert not any("position" in e for e in _page_data(page)) and "<option>dot</option>" not in page
    assert "<option>cose</option>" in page


def test_dot_text_clusters_a_loop_and_styles_the_edges():
    G, _ = build(workflow())
    dot = engines.to_dot(G)
    assert 'subgraph "cluster_lp"' in dot and '"lp/b"' in dot
    assert dot.count("style=dashed") >= 2 and "constraint=false" in dot       # data edges
    assert "shape=diamond" in dot                                             # EVALUATE
    assert "fixedsize" not in dot and "fixedsize=true" in engines.to_dot(G, fixed_size=True)


def test_graphviz_writes_svg_or_dot(tmp_path):
    if shutil.which("dot"):
        out, _, _ = engines.render(workflow(), tmp_path / "w.svg", "graphviz")
        assert out.read_text(encoding="utf-8").lstrip().startswith(("<?xml", "<svg"))
    else:
        with pytest.raises(RuntimeError, match="dot is not installed"):
            engines.render(workflow(), tmp_path / "w.svg", "graphviz")
        assert (tmp_path / "w.dot").exists()


def test_unknown_engine_and_empty_workflow(tmp_path):
    with pytest.raises(ValueError, match="unknown engine"):
        engines.render(workflow(), tmp_path / "x", "nope")
    with pytest.raises(ValueError, match="no nodes"):
        engines.render({"workflow": {"name": "e"}, "nodes": [], "edges": []}, tmp_path / "x.html")


def test_cli_vis_writes_the_file_and_reports_it(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("graphlang.grafv.cli.webbrowser.open", lambda url: opened.append(url))
    out = tmp_path / "cb.html"
    result = CliRunner().invoke(main, ["vis", str(CONCEPT_BOOK), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists() and "cytoscape: 7 nodes" in result.output and opened == [out.resolve().as_uri()]


def test_cli_vis_default_location_is_graflang_vis_in_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["vis", str(SELF_REFINE), "--no-open"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".graflang" / "vis" / "self_refine-cytoscape.html").exists()


def test_cli_vis_errors_are_messages_not_tracebacks(tmp_path):
    run = lambda *a: CliRunner().invoke(main, ["vis", *a, "--no-open"])  # noqa: E731
    assert run(str(tmp_path / "nope.yaml")).exit_code == 1
    bad = tmp_path / "bad.graph.yaml"
    bad.write_text("workflow: {name: x}\nnodes: []\nedges: []\n")
    result = run(str(bad), "-o", str(tmp_path / "o.html"))
    assert result.exit_code == 1 and "Invalid graph" in result.output and "Traceback" not in result.output
    assert CliRunner().invoke(main, ["vis"]).exit_code == 2


def test_cli_list_engines():
    result = CliRunner().invoke(main, ["vis", "--list-engines"])
    assert result.exit_code == 0 and "cytoscape" in result.output and "graphviz" in result.output and "(default)" in result.output


def test_graf_is_the_only_command_line():
    assert {n for n, c in main.commands.items() if not c.hidden} == {"run", "validate", "info", "compile", "check", "vis", "expand", "export-spl"}
    assert main.commands["viz"].hidden                      # `graf viz` is a hidden alias of `graf vis` (tests/test_cli_alias.py)
    scripts = (ROOT / "pyproject.toml").read_text().split("[project.scripts]")[1].split("[")[0]
    assert 'graf = "graphlang.cli:main"' in scripts and "grafr" not in scripts and "grafc" not in scripts


def test_engine_registry():
    assert set(engines.ENGINES) == {"cytoscape", "graphviz", "pyvis", "graphify", "mermaid", "ascii"}
    assert engines.DEFAULT_ENGINE == "cytoscape"


def test_mermaid_text_nests_loops_and_distinguishes_edges(tmp_path):
    out, _, n = engines.render(workflow(), tmp_path / "w.mmd", "mermaid")
    text = out.read_text(encoding="utf-8")
    assert n == 6 and text.startswith("flowchart LR")
    assert '(LOOP)"]' in text and "subgraph" in text and "\n  end\n" in text          # the loop is a box around b and c
    assert "-.->" in text and "-->" in text                                            # data vs control
    assert "classDef GENERATE" in text and "classDef LOOP" not in text                  # the loop box is not a node class
    assert "{" in text                                                                  # EVALUATE is a diamond
    md = engines.render(workflow(), tmp_path / "w.md", "mermaid")[0].read_text(encoding="utf-8")
    assert md.startswith("```mermaid\nflowchart LR") and md.endswith("```\n")


def test_mermaid_quotes_in_labels_do_not_break_the_syntax():
    G, _ = build({"workflow": {"name": "q"}, "nodes": [{"id": "a", "type": "INPUT", "ports": ["entry"]}], "edges": []})
    G.nodes["a"]["label"] = 'say "hi"'
    assert '"hi"' not in engines.to_mermaid_text(G) and "#quot;hi#quot;" in engines.to_mermaid_text(G)


def test_pyvis_engine_or_a_clear_install_hint(tmp_path):
    if engines.pyvis_ready()[0]:
        out, _, n = engines.render(workflow(), tmp_path / "p.html", "pyvis")
        page = out.read_text(encoding="utf-8")
        assert n == 6 and "<html" in page and "GENERATE" in page and "hierarchical" in page
    else:
        with pytest.raises(RuntimeError, match=r"graflang\[vis\]"):
            engines.render(workflow(), tmp_path / "p.html", "pyvis")


def test_graphify_engine_or_a_clear_install_hint(tmp_path):
    if engines.graphify_ready()[0]:
        out, _, n = engines.render(workflow(), tmp_path / "g.html", "graphify")
        assert n == 6 and out.stat().st_size > 1000
    else:
        with pytest.raises(RuntimeError, match=r"graflang\[graphify\]"):
            engines.render(workflow(), tmp_path / "g.html", "graphify")


def test_missing_optional_engine_is_reported_by_the_cli(tmp_path, monkeypatch):
    monkeypatch.setitem(engines.ENGINES["pyvis"], "ready", lambda: (False, "needs pyvis: pip install 'graflang[vis]'"))
    result = CliRunner().invoke(main, ["vis", str(SELF_REFINE), "--engine", "pyvis", "--no-open", "-o", str(tmp_path / "x.html")])
    assert result.exit_code == 1 and "graflang[vis]" in result.output and "Traceback" not in result.output
    listing = CliRunner().invoke(main, ["vis", "--list-engines"]).output
    assert "!!" in listing and "graflang[vis]" in listing


def test_mermaid_is_not_opened_in_a_browser(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("graphlang.grafv.cli.webbrowser.open", lambda url: opened.append(url))
    result = CliRunner().invoke(main, ["vis", str(SELF_REFINE), "--engine", "mermaid", "-o", str(tmp_path / "m.mmd")])
    assert result.exit_code == 0 and (tmp_path / "m.mmd").exists() and opened == []


def test_ascii_engine_is_available_through_zinet(tmp_path):
    out, _, n = engines.render(workflow(), tmp_path / "w.txt", "ascii")
    text = out.read_text(encoding="utf-8")
    assert n == 6 and text.startswith("Tier 0") and "[INPUT   ] start" in text and "[GENERATE] p  <- start" in text


def test_zinet_install_hints_are_shown_as_graflang_extras(tmp_path, monkeypatch):
    monkeypatch.setitem(engines.ENGINES["pyvis"], "ready", lambda: (False, "needs pyvis: pip install 'zinet[pyvis]'"))
    with pytest.raises(RuntimeError, match=r"graflang\[vis\]"):
        engines.render(workflow(), tmp_path / "p.html", "pyvis")
    result = CliRunner().invoke(main, ["vis", "--list-engines"])
    assert "graflang[vis]" in result.output and "zinet[" not in result.output
    assert engines.hint("pip install 'zinet[graphify]'") == "pip install 'graflang[graphify]'"


def test_the_style_reads_what_the_model_writes():
    G, _ = build(workflow())
    s = engines.graphlang_style("t")
    assert s.shape("start", G.nodes["start"]) == "round-rectangle" and s.shape("lp/c", G.nodes["lp/c"]) == "diamond"
    assert s.group("lp/b", G.nodes["lp/b"]) == "lp" and s.group("a", G.nodes["a"]) is None
    edge = next(d for u, v, d in G.edges(data=True) if d["relation"] == "binds")
    assert s.edge_dashed("", "", edge) and "→" in s.edge_info("", "", edge)


@pytest.mark.parametrize("args", [["-h"], ["--help"], ["run", "-h"], ["vis", "-h"], ["validate", "--help"]])
def test_short_and_long_help_work_on_graf_and_every_command(args):
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0 and "Usage:" in result.output


def test_the_page_starts_with_the_control_flow_and_loops_collapsed():
    G, _ = build(workflow())
    page = engines.cytoscape_html(G)
    assert json.loads(re.search(r"const OPTS = (\{.*?\});", page).group(1)) == {"dataHidden": True, "collapsed": True}
    assert 'id="showdata"' in page and "show data edges" in page and 'id="collapseall"' in page
    assert engines.graphlang_style().secondary_hidden and engines.graphlang_style().groups_collapsed


def _label(node):
    from graphlang.grafv.model import display_label
    return display_label({"ports": [], **node})


def test_display_labels_say_what_a_node_does():
    assert _label({"id": "gen_1", "type": "GENERATE", "config": {"function": "draft", "prompt_inline": "draft(@task)"}}) == "draft"
    assert _label({"id": "n", "type": "GENERATE", "config": {"prompt_ref": "prompts.critique"}}) == "critique"
    assert _label({"id": "tool_1", "type": "SOLVE", "config": {"tool": "write_file", "expression": "write_file(...)"}}) == "write file"
    assert _label({"id": "x", "type": "SOLVE", "config": {"procedure_ref": "procedures.run_tests"}}) == "run tests"
    assert _label({"id": "set_1", "type": "CONTEXT", "ports": ["trigger", "out_iteration"], "config": {"action": "set"}}) == "set iteration"
    assert _label({"id": "e", "type": "EVALUATE", "config": {"condition": "contains(@in_subject, '[APPROVED]')"}}) == "contains(subject, '[APPROVED]')"
    assert _label({"id": "l", "type": "LOOP", "config": {"condition": "@in_iteration < @in_max_iterations"}}) == "repeat while iteration < max iterat…"
    assert _label({"id": "wf_entry", "type": "INPUT"}) == "wf entry"                        # nothing better than the id, with spaces
    assert _label({"id": "g", "type": "GENERATE", "config": {"label": "Write the first draft", "function": "draft"}}) == "Write the first draft"


def test_the_id_stays_in_the_side_panel_and_search_still_finds_by_label():
    G, _ = build(workflow())
    assert G.nodes["a"]["info"].splitlines()[:2] == ["id: a", "type: GENERATE"]
    assert G.nodes["a"]["label"] == "p"


def test_nodes_show_no_type_line():
    assert engines.graphlang_style().show_kind is False


def test_underscores_become_spaces_but_an_explicit_label_is_left_alone():
    assert _label({"id": "write_draft_file", "type": "OUTPUT"}) == "write draft file"
    assert _label({"id": "x", "type": "GENERATE", "config": {"label": "keep_this_as_written"}}) == "keep_this_as_written"
    G, _ = build(workflow())
    assert "_" not in " ".join(d["label"] for _, d in G.nodes(data=True) if d["label"] != "p")   # ids stay in the panel, not on the node
