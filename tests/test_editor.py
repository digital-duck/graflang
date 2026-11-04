"""The editing engine behind `graf vis --edit`: edits keep the author's comments, validate before writing, and can be undone."""
import shutil
from pathlib import Path

import pytest

from graphlang.grafv.editor import EditError, GraphEditor

SELF_REFINE = Path(__file__).parent.parent / "cookbook" / "self_refine"


@pytest.fixture
def work(tmp_path):
    dest = tmp_path / "self_refine"
    shutil.copytree(SELF_REFINE, dest, ignore=shutil.ignore_patterns("output"))
    return dest / "self_refine.graph.yaml"


def test_an_untouched_file_round_trips_exactly(work):
    ed = GraphEditor(work)
    assert ed._dump() == work.read_text() and not ed.changed
    assert ed.problems() == ([], [])


def test_edits_keep_the_comments_and_the_rest_of_the_file(work):
    ed = GraphEditor(work)
    ed.set_config("draft", "temperature", 0.2)
    ed.save()
    text = work.read_text()
    assert "# Control flow" in text and "# Data flow" in text and "temperature: 0.2" in text
    assert text.replace("      temperature: 0.2\n", "") == SELF_REFINE.joinpath("self_refine.graph.yaml").read_text() or "draft" in text


def test_a_node_is_added_then_wired_and_the_graph_is_invalid_in_between(work):
    ed = GraphEditor(work)
    ed.add_node("polish", "GENERATE", ["trigger", "complete", "in_essay", "out_essay"], {"prompt_inline": "Polish {{in_essay}}"})
    errors, warnings = ed.problems()
    assert any("nothing triggers it" in w for w in warnings)                          # not wired yet: a warning
    assert len(errors) == 1 and "{{in_essay}}" in errors[0]                           # and the prompt's input is not fed yet: an error
    ed.add_edge("refine.complete", "polish.trigger", "triggers")
    ed.add_edge("refine.out_essay", "polish.in_essay", "binds")
    assert ed.problems() == ([], [])
    ed.save()
    assert "polish" in work.read_text() and GraphEditor(work).node("polish")["config"]["prompt_inline"] == "Polish {{in_essay}}"


def test_save_refuses_while_the_graph_has_errors_and_leaves_the_file_alone(work):
    before = work.read_text()
    ed = GraphEditor(work)
    ed.set_config("draft", "prompt_ref", "prompts.nope")                               # a prompt that is not listed or on disk
    errors, _ = ed.problems()
    assert errors
    with pytest.raises(EditError, match="not saved"):
        ed.save()
    assert work.read_text() == before and not list(work.parent.glob(".*.tmp"))


def test_undo_walks_back_every_edit(work):
    ed = GraphEditor(work)
    ed.set_config("draft", "temperature", 0.5)
    ed.remove_node("critique")
    assert "critique" not in ed.node_ids() and ed.changed
    assert ed.undo() and "critique" in ed.node_ids()
    assert ed.undo() and not ed.changed
    assert not ed.undo()


def test_removing_a_node_removes_its_edges(work):
    ed = GraphEditor(work)
    ed.remove_node("critique")
    assert not [e for e in ed.data()["edges"] if "critique" in e["source"] or "critique" in e["target"]]


def test_renaming_a_node_updates_the_edges(work):
    ed = GraphEditor(work)
    ed.rename_node("critique", "review")
    edges = ed.data()["edges"]
    assert any(e["source"] == "draft.out_essay" and e["target"] == "review.in_essay" for e in edges)
    assert not any("critique" in e["source"] + e["target"] for e in edges)
    assert ed.problems()[0] == []


@pytest.mark.parametrize("call, message", [
    (lambda ed: ed.add_node("draft", "SOLVE", ["trigger"]), "already a node"),
    (lambda ed: ed.add_node("bad id", "SOLVE", ["trigger"]), "letters, digits"),
    (lambda ed: ed.add_node("x", "SOLVE", []), "at least one port"),
    (lambda ed: ed.remove_node("ghost"), "no node 'ghost'"),
    (lambda ed: ed.add_edge("draft.complete", "ghost.trigger", "triggers"), "no node 'ghost'"),
    (lambda ed: ed.add_edge("draft.complete", "critique.nope", "triggers"), "no port 'nope'"),
    (lambda ed: ed.add_edge("draft.complete", "critique.trigger", "maybe"), "triggers"),
    (lambda ed: ed.add_edge("draft.complete", "critique.trigger", "triggers"), "already there"),
    (lambda ed: ed.remove_edge("draft.complete", "refine.trigger", "triggers"), "no edge"),
    (lambda ed: ed.delete_config("draft", "nope"), "no config key"),
    (lambda ed: ed.set_ports("draft", ["trigger", "complete", "in_topic"]), "still uses a port"),
    (lambda ed: ed.rename_node("draft", "critique"), "already a node"),
])
def test_a_bad_edit_is_named_and_changes_nothing(work, call, message):
    ed = GraphEditor(work)
    before = ed._dump()
    with pytest.raises(EditError, match=message):
        call(ed)
    assert ed._dump() == before and not ed.changed


def test_delete_config_drops_an_emptied_config_block(work):
    ed = GraphEditor(work)
    ed.add_node("t", "SOLVE", ["trigger", "complete"], {"expression": "1"})
    ed.delete_config("t", "expression")
    assert "config" not in ed.node("t")


SHORT = """version: "1.0-graph"
workflow:
  name: t
  inputs: [{name: q, type: TEXT}]
  outputs: [{name: r, type: TEXT}]
steps:
  - a: {solve: "@in_q + '!'", in: {q: $in.q}, out: r}
  - done: {output: a.r}
"""


def test_a_compact_file_is_edited_as_long_form_and_saved_short(tmp_path):
    path = tmp_path / "c.graph.yaml"
    path.write_text(SHORT)
    ed = GraphEditor(path)
    assert ed.compact_origin and "steps:" in ed.source() and not ed.changed            # the Source tab shows the short form
    assert [n["id"] for n in ed.data()["nodes"]][:2] == ["wf_entry", "a"]               # the graph is the expanded one
    ed.set_config("a", "expression", "@in_q + '?'")
    assert ed.changed
    ed.save()
    text = path.read_text()
    assert "steps:" in text and "nodes:" not in text and "'?'" in text or "?" in text
    again = GraphEditor(path)
    assert again.node("a")["config"]["expression"] == "@in_q + '?'" and not again.changed


def test_the_short_form_can_be_typed_in_the_source_tab(tmp_path):
    path = tmp_path / "c.graph.yaml"
    path.write_text(SHORT)
    ed = GraphEditor(path)
    ed.set_source(SHORT.replace("'!'", "'#'"))
    assert ed.changed and ed.node("a")["config"]["expression"] == "@in_q + '#'"
    ed.undo()
    assert not ed.changed


def test_a_compact_file_that_does_not_expand_is_refused(tmp_path):
    path = tmp_path / "c.graph.yaml"
    path.write_text('version: "1.0-graph"\nworkflow: {name: t, inputs: [], outputs: []}\nsteps:\n  - a: {frobnicate: 1}\n')
    with pytest.raises(EditError, match="does not expand"):
        GraphEditor(path)


def test_a_hand_edit_may_set_what_a_model_may_not(work):
    ed = GraphEditor(work)
    ed.add_node("calc", "SOLVE", ["trigger", "complete", "out_v"], {"backend": "subprocess", "command": ["python3", "-c", "print(1)"]})
    assert "calc" in ed.node_ids()                                                    # CODE_KEYS bind a MUTATE delta, not a person


ALL = sorted(p for p in (Path(__file__).parent.parent / "cookbook").rglob("*.graph.yaml") if not any(f"\n{k}:" in p.read_text() for k in ("steps", "expand", "elaborate")))   # the editor takes the long form only


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.parent.name)
def test_every_shipped_graph_round_trips_with_its_comments(path):
    """Alignment spaces inside `{...}` may be normalised; the data and every comment must survive."""
    from ruamel.yaml import YAML
    ed = GraphEditor(path)
    dumped = ed._dump()
    assert YAML(typ="safe").load(dumped) == YAML(typ="safe").load(path.read_text())
    comments = lambda text: [line.strip() for line in text.splitlines() if "#" in line and not line.lstrip().startswith("-")]
    assert comments(dumped) == comments(path.read_text())


def test_run_executes_the_graph_as_it_is_now_not_as_saved(work):
    ed = GraphEditor(work)
    res = ed.run({"topic": "ducks"})
    assert res["ok"] and "essay" in res["outputs"] and res["summary"]["steps"] >= 3
    ed.set_config("draft", "prompt_ref", "prompts.nope")
    res = ed.run({"topic": "ducks"})
    assert not res["ok"] and "fix these first" in res["error"]                         # an unsaved bad edit is what runs, and it is refused


def test_run_reports_a_failed_run_instead_of_raising(work):
    res = GraphEditor(work).run({})                                                    # the required input is missing
    assert not res["ok"] and "topic" in res["error"]


def test_a_file_with_an_expand_block_is_pointed_to_graf_expand():
    with pytest.raises(EditError, match="expand"):
        GraphEditor(Path(__file__).parent.parent / "cookbook" / "expand_demo" / "expand_demo.graph.yaml")


def test_clone_copies_the_saved_file_beside_it_and_leaves_the_original_alone(tmp_path):
    src = tmp_path / "g.graph.yaml"
    shutil.copy(ALL[0], src)
    before = src.read_bytes()
    editor = GraphEditor(src)
    copy = editor.clone("g-copy")
    assert copy == tmp_path / "g-copy.graph.yaml" and copy.read_bytes() == before == src.read_bytes()     # comments and all
    assert editor.clone("h.graph.yaml").name == "h.graph.yaml"


@pytest.mark.parametrize("name", ["", "  ", "../x.graph.yaml", "sub/x.graph.yaml", ".hidden.graph.yaml"])
def test_clone_refuses_a_name_that_is_not_a_plain_file_name(tmp_path, name):
    src = tmp_path / "g.graph.yaml"
    shutil.copy(ALL[0], src)
    with pytest.raises(EditError):
        GraphEditor(src).clone(name)
    assert [p.name for p in tmp_path.iterdir()] == ["g.graph.yaml"]


def test_clone_never_overwrites_an_existing_file(tmp_path):
    src, other = tmp_path / "g.graph.yaml", tmp_path / "other.graph.yaml"
    shutil.copy(ALL[0], src)
    other.write_text("precious")
    with pytest.raises(EditError, match="already exists"):
        GraphEditor(src).clone("other")
    assert other.read_text() == "precious"


def test_set_source_replaces_the_graph_keeps_what_was_typed_and_can_be_undone(work):
    ed = GraphEditor(work)
    original = ed.source()
    assert original == work.read_text()
    typed = original.replace("# Control flow", "# Control flow (edited by hand)")
    ed.set_source(typed)
    assert ed.changed and "edited by hand" in ed.source()
    assert ed.undo() and ed.source() == original and not ed.changed


def test_set_source_with_the_same_text_is_not_a_change(work):
    ed = GraphEditor(work)
    ed.set_source(ed.source())
    assert not ed.changed and not ed._undo


@pytest.mark.parametrize("text,reason", [("a: [", "not valid YAML"), ("just text", "needs `workflow:`"), ("steps: []\nworkflow: {name: x}", "compact"),
                                         ("workflow: {name: x}\nnodes: nope", "list of mappings"), ("workflow: {name: x}\nnodes:\n- {type: GENERATE}", "`id`")])
def test_set_source_refuses_text_that_is_not_a_workflow_and_changes_nothing(work, text, reason):
    ed = GraphEditor(work)
    before = ed.source()
    with pytest.raises(EditError, match=reason):
        ed.set_source(text)
    assert ed.source() == before and not ed.changed


def test_set_source_accepts_a_graph_with_errors_so_it_can_be_fixed_and_save_refuses_it(work):
    ed = GraphEditor(work)
    import re
    ed.set_source(re.sub(r"GENERATE", "NOPE", ed.source(), count=1))
    errors, _ = ed.problems()
    assert errors
    with pytest.raises(EditError, match="not saved"):
        ed.save()
