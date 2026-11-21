"""`graf describe --depth` and `graf info --depth`: the same levels `graf vis --depth` draws."""
from pathlib import Path

from click.testing import CliRunner

from graphlang.cli import main

CODE_PARTS = str(Path(__file__).resolve().parent.parent / "cookbook" / "code_parts" / "code_parts.graph.yaml")


def describe(*flags):
    r = CliRunner().invoke(main, ["describe", CODE_PARTS, "-o", "-", *flags])
    assert r.exit_code == 0, r.output
    return r.output


def test_depth_zero_closes_parts_and_loops_to_one_line_each():
    text = describe("--depth", "0")
    assert "**analyze** (part `analyze_spec`) holds 1 step; open it" in text
    assert "**repair** (LOOP)" in text and "holds 5 steps; open it" in text
    assert "analyze__gen" not in text and "**improve**" not in text                  # nothing from inside a closed box leaks into the text


def test_reads_from_a_closed_part_name_the_part_not_its_inner_node():
    text = describe("--depth", "0")
    assert "analysis (from analyze's analysis)" in text


def test_all_is_the_default_and_opens_everything():
    full = describe()
    assert full == describe("--depth", "all")
    assert "analyze__gen" in full and "**improve**" in full


def test_depth_one_opens_the_top_level_boxes():
    text = describe("--depth", "1")
    assert "analyze__gen" in text and "**improve**" in text and "open it with a larger --depth" not in text


def test_describe_depth_is_refused_with_llm_and_when_bad():
    r = CliRunner().invoke(main, ["describe", CODE_PARTS, "-o", "-", "--depth", "0", "--llm", "mock"])
    assert r.exit_code == 1 and "cannot be used with --llm" in r.output
    assert CliRunner().invoke(main, ["describe", CODE_PARTS, "-o", "-", "--depth", "-2"]).exit_code != 0


def test_info_depth_shows_counts_and_the_closed_boxes():
    r = CliRunner().invoke(main, ["info", CODE_PARTS, "--depth", "0"])
    assert r.exit_code == 0, r.output
    assert "Nodes at depth 0" in r.output and "repair (LOOP): 5 nodes inside" in r.output and "analyze (SUBGRAPH): 1 node inside" in r.output
    plain = CliRunner().invoke(main, ["info", CODE_PARTS]).output
    assert "depth" not in plain                                                  # without the option nothing changes
    full = CliRunner().invoke(main, ["info", CODE_PARTS, "--depth", "all"]).output
    assert "Closed" not in full and "Nodes at depth all" in full


def test_info_depth_rejects_a_bad_value():
    r = CliRunner().invoke(main, ["info", CODE_PARTS, "--depth", "deep"])
    assert r.exit_code == 1 and "whole number" in r.output


# ---- a composite inside a composite: every level is its own depth ------------------------------------------------------------

def nested(tmp_path):
    import shutil
    dst = tmp_path / "cp"
    shutil.copytree(Path(CODE_PARTS).parent, dst, ignore=shutil.ignore_patterns("output"))
    r = CliRunner().invoke(main, ["group", str(dst / "code_parts.graph.yaml"), "--nodes", "write,review", "--name", "wr"])
    assert r.exit_code == 0, r.output
    return str(dst / "code_parts.graph.yaml")


def info_rows(graph, depth):
    out = CliRunner().invoke(main, ["info", graph, "--depth", depth]).output
    nodes = int(next(line for line in out.splitlines() if "Nodes at depth" in line).split("│")[2])
    closed = [line.split("│")[2].strip() for line in out.splitlines() if "Closed" in line]
    return nodes, closed


def test_each_level_of_nested_composites_is_a_depth(tmp_path):
    g = nested(tmp_path)
    n0, closed0 = info_rows(g, "0")
    n1, closed1 = info_rows(g, "1")
    n2, closed2 = info_rows(g, "2")
    nall, closed_all = info_rows(g, "all")
    assert n0 < n1 < n2 == nall                                                  # the inner level is a depth of its own
    assert "wr (SUBGRAPH): 2 nodes inside" in closed0                           # the two steps of write and review, not their boxes
    assert closed1 == ["wr__write (SUBGRAPH): 1 node inside", "wr__review (SUBGRAPH): 1 node inside"]
    assert closed2 == [] == closed_all


def test_describe_follows_the_nesting_too(tmp_path):
    g = nested(tmp_path)
    r0 = CliRunner().invoke(main, ["describe", g, "-o", "-", "--depth", "0"]).output
    r1 = CliRunner().invoke(main, ["describe", g, "-o", "-", "--depth", "1"]).output
    r2 = CliRunner().invoke(main, ["describe", g, "-o", "-", "--depth", "2"]).output
    assert "**wr** (part `wr`) holds 2 steps" in r0
    assert "**wr__write** (part `write_code`) holds 1 step" in r1 and "**wr__review**" in r1
    assert "wr__write__gen" in r2 and "holds 1 step" not in r2.split("repair")[0]


def test_vis_draws_the_inner_level_as_a_box_inside_the_outer_one(tmp_path):
    from graphlang.grafr.runtime import load_graph
    from graphlang.grafv.model import build
    g = load_graph(nested(tmp_path))
    G, _ = build(g, None)
    assert G.nodes["wr__write"]["parent"] == "wr" and G.nodes["wr"].get("parent") is None
    assert any(d.get("parent") == "wr__write" for _, d in G.nodes(data=True))


def test_graf_expand_drops_the_loaders_bookkeeping(tmp_path):
    out = CliRunner().invoke(main, ["expand", nested(tmp_path)]).output
    assert "_part_of" not in out and "_use_parent" not in out and "_source_dir" not in out
