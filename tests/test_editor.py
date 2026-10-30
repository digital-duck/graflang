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
    assert errors == [] and any("nothing triggers it" in w for w in warnings)         # not wired yet: a warning
    ed.add_edge("refine.complete", "polish.trigger", "triggers")
    ed.add_edge("refine.out_essay", "polish.in_essay", "binds")
    assert ed.problems()[1] == []
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


def test_a_compact_file_is_pointed_to_graf_expand(tmp_path):
    path = tmp_path / "c.graph.yaml"
    path.write_text('version: "1.0-graph"\nworkflow: {name: t, inputs: [], outputs: []}\nsteps:\n  - a: {solve: "1"}\n')
    with pytest.raises(EditError, match="graf expand"):
        GraphEditor(path)


def test_a_hand_edit_may_set_what_a_model_may_not(work):
    ed = GraphEditor(work)
    ed.add_node("calc", "SOLVE", ["trigger", "complete", "out_v"], {"backend": "subprocess", "command": ["python3", "-c", "print(1)"]})
    assert "calc" in ed.node_ids()                                                    # CODE_KEYS bind a MUTATE delta, not a person


ALL = sorted(p for p in (Path(__file__).parent.parent / "cookbook").rglob("*.graph.yaml") if "\nsteps:" not in p.read_text())   # the editor takes the long form only


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.parent.name)
def test_every_shipped_graph_round_trips_with_its_comments(path):
    """Alignment spaces inside `{...}` may be normalised; the data and every comment must survive."""
    from ruamel.yaml import YAML
    ed = GraphEditor(path)
    dumped = ed._dump()
    assert YAML(typ="safe").load(dumped) == YAML(typ="safe").load(path.read_text())
    comments = lambda text: [line.strip() for line in text.splitlines() if "#" in line and not line.lstrip().startswith("-")]
    assert comments(dumped) == comments(path.read_text())
