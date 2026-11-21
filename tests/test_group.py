"""Group: a selection of nodes becomes a composite, a part in a subfolder; the flattened graph behaves as before."""
import pytest
import yaml

from graphlang.grafr.compact import expand
from graphlang.grafr.group import GroupError, group, write_group
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check
from graphlang.yamlfmt import dump_readable

SRC = """
version: "1.0-graph"
workflow:
  name: calc
  inputs: [{name: n, type: INTEGER}]
  outputs: [{name: result, type: INTEGER}]
steps:
  - a: {solve: "@in_n + 1", in: {n: $in.n}, out: v}
  - b: {solve: "@in_n * 2", in: {n: a.v}, out: v}
  - c: {solve: "@in_n + 10", in: {n: b.v}, out: v}
  - done: {output: {result: c.v}}
"""


def long_form():
    return expand(yaml.safe_load(SRC))


def run(path, n=3):
    g = load_graph(path)
    return GraphLangRuntime(g, verbose=False).execute({"n": n})


def test_grouping_two_steps_keeps_the_answer(tmp_path):
    original = tmp_path / "orig.graph.yaml"
    original.write_text(dump_readable(long_form()))
    want = run(original)
    parent, part, files = group(long_form(), ["b", "c"], "tail")
    (tmp_path / "app").mkdir()
    graph = tmp_path / "app" / "calc.graph.yaml"
    graph.write_text(dump_readable(parent))
    assert write_group(graph.parent, "tail", part, files, graph.parent) == graph.parent / "tail" / "tail.graph.yaml"
    assert [n["id"] for n in parent["nodes"] if n["type"] == "SUBGRAPH"] == ["tail"]
    assert parent["resources"]["parts"]["tail"] == "./tail/tail.graph.yaml"
    assert run(graph) == want == {"result": 18}
    errors, _ = check(load_graph(graph))
    assert errors == []


def test_the_part_has_the_interface_of_the_cut():
    _, part, _ = group(long_form(), ["b", "c"], "tail")
    assert [i["name"] for i in part["workflow"]["inputs"]] == ["n"]
    assert [o["name"] for o in part["workflow"]["outputs"]] == ["v"]


def test_two_entries_are_refused():
    g = long_form()
    # a second outside trigger into c (not b): the selection would have two entries
    g["edges"].append({"source": "a.complete", "target": "c.trigger", "type": "triggers"})
    with pytest.raises(GroupError, match="exactly one entry"):
        group(g, ["b", "c"], "tail")


def test_the_workflows_input_and_output_nodes_cannot_be_grouped():
    with pytest.raises(GroupError, match="INPUT"):
        group(long_form(), ["wf_entry", "a"], "head")


def test_a_taken_name_is_refused():
    with pytest.raises(GroupError, match="already used"):
        group(long_form(), ["b", "c"], "a")


def test_a_prompt_goes_with_the_node_that_uses_it(tmp_path):
    g = long_form()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "say.md").write_text("Say {{in_n}}")
    g["resources"] = {"prompts": {"say": "./prompts/say.md"}}
    b = next(n for n in g["nodes"] if n["id"] == "b")
    b["type"], b["config"] = "GENERATE", {"prompt_ref": "prompts.say"}
    b["ports"] = ["trigger", "complete", "in_n", "out_v"]
    parent, part, files = group(g, ["b", "c"], "tail")
    assert files == [("prompts", "say", "./prompts/say.md")]
    assert "prompts" not in parent["resources"]
    write_group(tmp_path, "tail", part, files, tmp_path)
    assert (tmp_path / "tail" / "prompts" / "say.md").read_text() == "Say {{in_n}}"
    assert part["resources"]["prompts"]["say"] == "./prompts/say.md"


def test_an_existing_folder_is_never_overwritten(tmp_path):
    (tmp_path / "tail").mkdir()
    _, part, files = group(long_form(), ["b", "c"], "tail")
    with pytest.raises(GroupError, match="already exists"):
        write_group(tmp_path, "tail", part, files, tmp_path)


def test_graf_group_writes_the_subfolder_and_keeps_a_compact_file_compact(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    graph = tmp_path / "calc.graph.yaml"
    graph.write_text(SRC)
    r = CliRunner().invoke(main, ["group", str(graph), "--nodes", "b,c", "--name", "tail"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "tail" / "tail.graph.yaml").is_file()
    text = graph.read_text()
    assert "steps:" in text and "tail" in text and "solve: \"@in_n * 2\"" not in text
    assert run(graph) == {"result": 18}


def test_graf_group_dry_run_and_refusal_write_nothing(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    graph = tmp_path / "calc.graph.yaml"
    graph.write_text(SRC)
    r = CliRunner().invoke(main, ["group", str(graph), "--nodes", "b,c", "--name", "tail", "--dry-run"])
    assert r.exit_code == 0 and "inputs: n; outputs: v" in r.output
    r = CliRunner().invoke(main, ["group", str(graph), "--nodes", "b", "--name", "a"])
    assert r.exit_code == 1 and "already used" in r.output
    assert graph.read_text() == SRC and sorted(p.name for p in tmp_path.iterdir()) == ["calc.graph.yaml"]


def test_grouping_uses_of_parts_keeps_the_flat_graph_the_same_size(tmp_path):
    import shutil
    from pathlib import Path
    from click.testing import CliRunner
    from graphlang.cli import main
    src = Path(__file__).resolve().parent.parent / "cookbook" / "parts_demo"
    dst = tmp_path / "parts_demo"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("output"))
    before = load_graph(dst / "parts_demo.graph.yaml")
    r = CliRunner().invoke(main, ["group", str(dst / "parts_demo.graph.yaml"), "--nodes", "first,second", "--name", "polish_twice"])
    assert r.exit_code == 0, r.output
    after = load_graph(dst / "parts_demo.graph.yaml")
    assert (len(after["nodes"]), len(after["edges"])) == (len(before["nodes"]), len(before["edges"]))
    assert check(after)[0] == []
    inner = yaml.safe_load((dst / "polish_twice" / "polish_twice.graph.yaml").read_text())
    assert inner["resources"]["parts"]["polish"] == "../sub_graph/polish.graph.yaml"        # read from the subfolder
