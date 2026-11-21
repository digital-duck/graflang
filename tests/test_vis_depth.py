"""`graf vis --depth N`: open N levels of composites (parts) and loop bodies; the rest is one node each, links kept."""
from pathlib import Path

import pytest

from graphlang.grafr.runtime import load_graph
from graphlang.grafv.model import build

CODE_PARTS = Path(__file__).resolve().parent.parent / "cookbook" / "code_parts" / "code_parts.graph.yaml"


def sizes():
    g = load_graph(CODE_PARTS)
    return {d: build(g, d)[0] for d in (0, 1, 2, None)}


def test_more_depth_shows_more_nodes_and_none_is_everything():
    s = sizes()
    n = {d: G.number_of_nodes() for d, G in s.items()}
    assert n[0] < n[1] <= n[2] <= n[None]
    assert n[None] == build(load_graph(CODE_PARTS))[0].number_of_nodes()


def test_depth_zero_is_the_top_level_with_each_composite_one_node():
    G = sizes()[0]
    assert not any(d.get("parent") for _, d in G.nodes(data=True))           # nothing is nested any more
    names = {n for n in G.nodes}
    assert {"analyze", "write", "review", "repair"} <= names               # the three part uses and the loop are single nodes
    assert G.nodes["repair"]["label"].endswith("· 5 nodes") and G.nodes["write"]["label"].endswith("· 1 node")
    assert G.nodes["write"]["collapsed_nodes"] >= 1


def test_links_across_a_closed_box_end_at_the_box():
    G = sizes()[0]
    assert G.has_edge("analyze", "repair") or any(G.has_edge(a, "repair") for a in G.nodes)
    assert all(u in G and v in G for u, v in G.edges())
    # data from the top level reaches the loop's box rather than a node inside it
    assert any(v == "repair" and d["relation"] == "binds" for _, v, d in G.edges(data=True))


def test_depth_one_opens_the_top_level_boxes_and_closes_the_ones_inside():
    G = sizes()[1]
    assert any(d.get("parent") == "write" for _, d in G.nodes(data=True))     # the part is open
    # a box that sits inside another box is closed at depth 1
    inner = [n for n, d in G.nodes(data=True) if d.get("collapsed_nodes")]
    assert all(G.nodes[n].get("parent") for n in inner) or not inner


def test_cli_depth_flag_is_taken_and_validated(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    out, default, full = tmp_path / "v.html", tmp_path / "d.html", tmp_path / "all.html"
    r = CliRunner().invoke(main, ["vis", str(CODE_PARTS), "--depth", "0", "--no-open", "-o", str(out)])
    assert r.exit_code == 0, r.output
    assert CliRunner().invoke(main, ["vis", str(CODE_PARTS), "--no-open", "-o", str(default)]).exit_code == 0
    assert CliRunner().invoke(main, ["vis", str(CODE_PARTS), "--depth", "all", "--no-open", "-o", str(full)]).exit_code == 0
    assert default.read_text() == out.read_text()                              # no flag means --depth 0
    assert out.stat().st_size < full.stat().st_size                           # fewer nodes, a smaller page
    for bad in ("-1", "deep"):
        assert CliRunner().invoke(main, ["vis", str(CODE_PARTS), "--depth", bad, "--no-open"]).exit_code != 0
