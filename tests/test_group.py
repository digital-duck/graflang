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


# ---- the editor ---------------------------------------------------------------------------------------------------

def _editor(tmp_path):
    from graphlang.grafv.editor import GraphEditor
    graph = tmp_path / "calc.graph.yaml"
    graph.write_text(dump_readable(long_form()))
    return GraphEditor(graph), graph


def test_editor_group_changes_the_graph_in_memory_and_writes_only_the_new_folder(tmp_path):
    ed, graph = _editor(tmp_path)
    before = graph.read_text()
    folder = ed.group(["b", "c"], "tail")
    assert folder == tmp_path / "tail" and (folder / "tail.graph.yaml").is_file()
    assert graph.read_text() == before and ed.changed                   # the file is untouched until Save
    assert [n["id"] for n in ed.data()["nodes"] if n["type"] == "SUBGRAPH"] == ["tail"]
    assert ed.problems()[0] == []
    ed.save()
    assert run(graph) == {"result": 18}


def test_editor_undo_removes_the_folder_the_group_made(tmp_path):
    ed, graph = _editor(tmp_path)
    ed.group(["b", "c"], "tail")
    assert ed.undo() and not (tmp_path / "tail").exists()
    assert [n["id"] for n in ed.data()["nodes"] if n["type"] == "SUBGRAPH"] == []


def test_editor_save_keeps_the_folder_from_a_later_undo(tmp_path):
    ed, graph = _editor(tmp_path)
    ed.group(["b", "c"], "tail")
    ed.save()
    ed.undo()                                                           # an undo after Save must not delete a folder the saved graph uses
    assert (tmp_path / "tail" / "tail.graph.yaml").is_file()


def test_editor_refuses_a_bad_selection_and_changes_nothing(tmp_path):
    from graphlang.grafv.editor import EditError
    ed, _ = _editor(tmp_path)
    with pytest.raises(EditError, match="already used"):
        ed.group(["b", "c"], "a")
    assert not ed.changed and not (tmp_path / "a").exists()


# ---- ungroup ------------------------------------------------------------------------------------------------------

def _same_graph(a, b):
    key = lambda e: (e["source"], e["target"], e["type"])      # noqa: E731
    na = {n["id"]: (n["type"], n.get("config")) for n in a["nodes"]}
    nb = {n["id"]: (n["type"], n.get("config")) for n in b["nodes"]}
    return na == nb and sorted(map(key, a["edges"])) == sorted(map(key, b["edges"]))


def test_ungroup_gives_back_the_original_graph(tmp_path):
    from graphlang.grafr.group import ungroup
    original = long_form()
    parent, part, files = group(original, ["b", "c"], "tail")
    write_group(tmp_path, "tail", part, files, tmp_path)
    graph = tmp_path / "calc.graph.yaml"
    graph.write_text(dump_readable(parent))
    back = ungroup(parent, "tail", tmp_path)
    assert _same_graph(back, original)
    assert "parts" not in back.get("resources", {}) and (tmp_path / "tail").is_dir()          # the folder is kept


def test_ungroup_brings_the_prompt_back_by_path(tmp_path):
    from graphlang.grafr.group import ungroup
    g = long_form()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "say.md").write_text("Say {{in_n}}")
    g["resources"] = {"prompts": {"say": "./prompts/say.md"}}
    b = next(n for n in g["nodes"] if n["id"] == "b")
    b["type"], b["config"], b["ports"] = "GENERATE", {"prompt_ref": "prompts.say"}, ["trigger", "complete", "in_n", "out_v"]
    parent, part, files = group(g, ["b", "c"], "tail")
    write_group(tmp_path, "tail", part, files, tmp_path)
    back = ungroup(parent, "tail", tmp_path)
    assert next(n for n in back["nodes"] if n["id"] == "b")["config"]["prompt_ref"] == "prompts.say"
    assert back["resources"]["prompts"]["say"] == "./tail/prompts/say.md"
    assert (tmp_path / back["resources"]["prompts"]["say"]).read_text() == "Say {{in_n}}"


def test_ungroup_a_name_that_is_taken_keeps_the_prefixed_id(tmp_path):
    from graphlang.grafr.group import ungroup
    parent, part, files = group(long_form(), ["b", "c"], "tail")
    write_group(tmp_path, "tail", part, files, tmp_path)
    parent["nodes"].append({"id": "b", "type": "OUTPUT", "ports": ["trigger", "exit"]})          # a new `b` appears at this level
    back = ungroup(parent, "tail", tmp_path)
    ids = {n["id"] for n in back["nodes"]}
    assert {"b", "tail__b", "c"} <= ids


def test_ungroup_refuses_a_node_that_is_not_a_composite(tmp_path):
    from graphlang.grafr.group import ungroup
    with pytest.raises(GroupError, match="not a composite"):
        ungroup(long_form(), "a", tmp_path)


def test_editor_ungroup_is_undoable(tmp_path):
    ed, graph = _editor(tmp_path)
    ed.group(["b", "c"], "tail")
    ed.ungroup("tail")
    assert [n["id"] for n in ed.data()["nodes"] if n["type"] == "SUBGRAPH"] == [] and ed.problems()[0] == []
    assert ed.undo()
    assert [n["id"] for n in ed.data()["nodes"] if n["type"] == "SUBGRAPH"] == ["tail"]


def test_group_then_ungroup_uses_of_parts_gives_the_same_flat_graph(tmp_path):
    import shutil
    from pathlib import Path
    from click.testing import CliRunner
    from graphlang.cli import main
    dst = tmp_path / "parts_demo"
    shutil.copytree(Path(__file__).resolve().parent.parent / "cookbook" / "parts_demo", dst, ignore=shutil.ignore_patterns("output"))
    graph = dst / "parts_demo.graph.yaml"
    before = load_graph(graph)
    assert CliRunner().invoke(main, ["group", str(graph), "--nodes", "first,second", "--name", "twice"]).exit_code == 0
    r = CliRunner().invoke(main, ["ungroup", str(graph), "--node", "twice"])
    assert r.exit_code == 0, r.output
    after = load_graph(graph)
    assert sorted(n["id"] for n in after["nodes"]) == sorted(n["id"] for n in before["nodes"])
    assert len(after["edges"]) == len(before["edges"])


def test_ungroup_keeps_the_parts_own_uses_as_uses(tmp_path):
    import shutil
    from pathlib import Path
    from graphlang.grafr.compact import expand
    from graphlang.grafr.group import ungroup
    src = Path(__file__).resolve().parent.parent / "cookbook" / "code_parts"
    dst = tmp_path / "cp"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("output"))
    data = expand(yaml.safe_load((dst / "code_parts.graph.yaml").read_text()))
    parent, part, files = group(data, ["write", "review"], "wr")
    write_group(dst, "wr", part, files, dst)
    back = ungroup(parent, "wr", dst)
    assert {n["id"] for n in back["nodes"] if n["type"] == "SUBGRAPH"} == {"analyze", "write", "review"}
    assert _same_graph({**back, "nodes": [n for n in back["nodes"]]}, {**data})
    assert back["resources"]["parts"]["write_code"] == data["resources"]["parts"]["write_code"]


# ---- several ways out: the failures become named error exits -----------------------------------------------------------------

BRANCHY = """
version: "1.0-graph"
workflow:
  name: sign
  inputs: [{name: n, type: INTEGER}]
  outputs: [{name: result, type: TEXT}]
steps:
  - check: {evaluate: "@in_n > 0", in: {n: $in.n}}
  - twice: {solve: "str(@in_n * 2)", in: {n: $in.n}, on: check.pass, out: v}
  - sorry: {solve: "'negative'", on: check.fail, out: r}
  - done: {output: {result: twice.v}, on: twice}
  - done2: {output: {result: sorry.r}, on: sorry}
"""


def branchy():
    from ruamel.yaml import YAML
    return expand(YAML(typ="safe").load(BRANCHY))          # YAML 1.2, as the app reads files: PyYAML would read `on:` as True


def test_two_different_ways_out_are_refused_unless_one_is_named_an_error_exit():
    data = branchy()
    with pytest.raises(GroupError, match="several ways out"):
        group(data, ["check", "twice"], "front")
    with pytest.raises(GroupError, match="not a control port that leaves"):
        group(data, ["check", "twice"], "front", exits={"bad": ["check.nope"]})
    with pytest.raises(GroupError, match="must stay the normal one"):
        group(data, ["check", "twice"], "front", exits={"a": ["check.fail"], "b": ["twice.complete"]})
    with pytest.raises(GroupError, match="lead to different nodes; give each its own name"):
        group(data, ["check", "twice"], "front", exits={"bad": ["check.fail", "twice.complete"]})


def test_a_named_exit_becomes_an_error_exit_and_the_answer_is_unchanged(tmp_path):
    from graphlang.grafr.runtime import GraphLangRuntime
    original = tmp_path / "orig.graph.yaml"
    original.write_text(BRANCHY)
    want = {n: GraphLangRuntime(load_graph(original), verbose=False).execute({"n": n}) for n in (4, -2)}
    folder = tmp_path / "app"
    folder.mkdir()
    graph = folder / "sign.graph.yaml"
    graph.write_text(BRANCHY)
    from click.testing import CliRunner
    from graphlang.cli import main
    r = CliRunner().invoke(main, ["group", str(graph), "--nodes", "check,twice", "--name", "front", "--exit", "negative=check.fail"])
    assert r.exit_code == 0, r.output
    part = yaml.safe_load((folder / "front" / "front.graph.yaml").read_text())
    assert [e["name"] for e in part["workflow"]["errors"]] == ["negative"]
    assert any((n.get("config") or {}).get("exit") == "negative" for n in part["nodes"])
    got = {n: GraphLangRuntime(load_graph(graph), verbose=False).execute({"n": n}) for n in (4, -2)}
    assert got == want == {4: {"result": "8"}, -2: {"result": "negative"}}
    assert check(load_graph(graph))[0] == []
    assert "negative" in graph.read_text()                                      # the use's `ports: [negative]` and its `on:`


def test_graf_group_rejects_a_malformed_exit(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    graph = tmp_path / "sign.graph.yaml"
    graph.write_text(BRANCHY)
    r = CliRunner().invoke(main, ["group", str(graph), "--nodes", "check,twice", "--name", "front", "--exit", "oops"])
    assert r.exit_code == 1 and "NAME=node.port" in r.output
    assert graph.read_text() == BRANCHY and not (tmp_path / "front").exists()


def test_ungroup_of_a_composite_with_an_error_exit_gives_the_original_graph(tmp_path):
    from graphlang.grafr.group import ungroup
    original = branchy()
    parent, part, files = group(original, ["check", "twice"], "front", exits={"negative": ["check.fail"]})
    write_group(tmp_path, "front", part, files, tmp_path)
    back = ungroup(parent, "front", tmp_path)
    assert _same_graph(back, original)


# ---- the interface keeps the types the graph declares ---------------------------------------------------------------------

def test_a_grouped_part_keeps_the_types_of_its_inputs_and_outputs():
    # `n` is an INTEGER workflow input and `a` takes it straight from there: the interface says INTEGER; the output of `b` is untyped: TEXT
    _, part, _ = group(long_form(), ["a", "b"], "head")
    assert [(i["name"], i["type"]) for i in part["workflow"]["inputs"]] == [("n", "INTEGER")]
    assert [(o["name"], o["type"]) for o in part["workflow"]["outputs"]] == [("v", "TEXT")]


def test_a_typed_port_gives_the_interface_its_type():
    g = long_form()
    c = next(n for n in g["nodes"] if n["id"] == "c")
    c["ports"] = {"trigger": "CONTROL", "complete": "CONTROL", "in_n": "INTEGER", "out_v": "FLOAT!"}
    _, part, _ = group(g, ["b", "c"], "tail")
    assert [(o["name"], o["type"]) for o in part["workflow"]["outputs"]] == [("v", "FLOAT")]


def test_editor_group_takes_a_description_and_exits(tmp_path):
    from graphlang.grafv.editor import GraphEditor
    graph = tmp_path / "sign.graph.yaml"
    graph.write_text(dump_readable(branchy()))
    ed = GraphEditor(graph)
    ed.group(["check", "twice"], "front", "doubles a positive number", {"negative": ["check.fail"]})
    part = yaml.safe_load((tmp_path / "front" / "front.graph.yaml").read_text())
    assert part["workflow"]["description"] == "doubles a positive number" and [e["name"] for e in part["workflow"]["errors"]] == ["negative"]
    assert ed.problems()[0] == []
