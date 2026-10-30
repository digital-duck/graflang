"""Compact authoring form (design E3): `steps:` desugars to nodes and edges, and the result runs like a hand-written graph."""
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from graphlang.cli import main
from graphlang.grafr.compact import CompactError, expand
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

from test_lifecycle import Scripted


def doc(steps, inputs=("topic",), outputs=("essay",), **extra):
    return {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [{"name": n, "type": "TEXT"} for n in inputs],
                                                  "outputs": [{"name": n, "type": "TEXT"} for n in outputs]},
            "steps": steps, **extra}


def edge_set(g):
    return {(e["source"], e["target"], e["type"]) for e in g["edges"]}


CHAIN = [{"draft": {"generate": "Write {{in_topic}}", "in": {"topic": "$in.topic"}, "out": "essay"}},
         {"critique": {"generate": "Critique {{in_essay}}", "in": {"essay": "draft"}, "out": "feedback"}},
         {"refine": {"generate": "Fix {{in_essay}} by {{in_feedback}} ({{in_tone}})", "out": "essay",
                     "in": {"essay": "draft", "feedback": "critique", "tone": "plain"}}},
         {"done": {"output": "refine"}}]


def test_a_chain_expands_to_the_edges_you_would_write_by_hand():
    g = expand(doc(CHAIN))
    assert edge_set(g) == {
        ("wf_entry.entry", "draft.trigger", "triggers"), ("draft.complete", "critique.trigger", "triggers"),
        ("critique.complete", "refine.trigger", "triggers"), ("refine.complete", "done.trigger", "triggers"),
        ("wf_entry.out_topic", "draft.in_topic", "binds"), ("draft.out_essay", "critique.in_essay", "binds"),
        ("draft.out_essay", "refine.in_essay", "binds"), ("critique.out_feedback", "refine.in_feedback", "binds"),
        ("refine.out_essay", "done.in_essay", "binds")}
    refine = next(n for n in g["nodes"] if n["id"] == "refine")
    assert refine["config"]["phases"]["pre"]["defaults"] == {"in_tone": "plain"}      # the literal is the input's default


def test_a_compact_file_loads_validates_and_runs(tmp_path):
    path = tmp_path / "c.graph.yaml"
    YAML().dump(doc(CHAIN), path)
    graph = load_graph(path)
    assert check(graph) == ([], [])
    llm = Scripted("D", "C", "F")
    assert GraphLangRuntime(graph, llm=llm, verbose=False).execute({"topic": "tides"}) == {"essay": "F"}
    assert llm.prompts == ["Write tides", "Critique D", "Fix D by C (plain)"]


def test_branches_hang_on_a_control_port_with_on():
    steps = [{"gate": {"assert": "@in_n > 3", "in": {"n": "$in.n"}}},
             {"big": {"solve": "'big'", "out": "v"}},
             {"small": {"solve": "'small'", "out": "v", "on": "gate.fail"}}]
    g = expand(doc(steps, inputs=("n",), outputs=()))
    assert ("gate.pass", "big.trigger", "triggers") in edge_set(g) and ("gate.fail", "small.trigger", "triggers") in edge_set(g)
    assert not any(e[1] == "small.trigger" and e[0] == "big.complete" for e in edge_set(g))


def test_fork_and_join():
    steps = [{"f": {"fork": ["left", "right"]}},
             {"a": {"solve": "1", "on": "f.left", "out": "v"}},
             {"b": {"solve": "2", "on": "f.right", "out": "v"}},
             {"j": {"join": ["a", "b"]}},
             {"sum": {"solve": "@in_x + @in_y", "in": {"x": "a", "y": "b"}, "out": "total"}},
             {"done": {"output": {"essay": "sum.total"}}}]
    g = expand(doc(steps, inputs=(), outputs=("essay",)))
    assert {("a.complete", "j.trigger", "triggers"), ("b.complete", "j.trigger", "triggers"),
            ("j.complete", "sum.trigger", "triggers")} <= edge_set(g)
    assert check(g) == ([], [])
    assert GraphLangRuntime(g, verbose=False).execute({}) == {"essay": 3}


def test_the_long_form_may_sit_beside_the_steps():
    raw = {"id": "tail", "type": "SOLVE", "config": {"expression": "@in_x"}, "ports": ["trigger", "complete", "in_x", "out_y"]}
    g = expand(doc([{"a": {"solve": "5", "out": "v"}}], nodes=[raw],
                   edges=[{"source": "a.out_v", "target": "tail.in_x", "type": "binds"},
                          {"source": "a.complete", "target": "tail.trigger", "type": "triggers"}]))
    assert [n["id"] for n in g["nodes"]] == ["wf_entry", "a", "tail"] and len(g["edges"]) == 3


def test_node_is_the_escape_hatch_for_other_types():
    g = expand(doc([{"m": {"node": "LOOP", "ports": ["trigger", "exit"], "config": {"max_iterations": 1, "subgraph": {"nodes": [], "edges": []}}}}]))
    loop = next(n for n in g["nodes"] if n["id"] == "m")
    assert loop["type"] == "LOOP" and {"trigger", "exit"} <= set(loop["ports"]) and loop["config"]["max_iterations"] == 1


@pytest.mark.parametrize("steps, message", [
    ([{"a": {"generate": "x", "solve": "1"}}], "exactly one of"),
    ([{"a": {"generate": "x", "in": {"t": "$in.nope"}}}], "not a workflow input"),
    ([{"a": {"generate": "x"}}, {"b": {"generate": "y", "in": {"t": "a.zzz"}}}], "has no result 'zzz'"),
    ([{"a": {"generate": "x", "on": "ghost.complete"}}], "names no earlier step"),
    ([{"f": {"fork": ["l"]}}, {"a": {"solve": "1"}}], "follows the fork"),
    ([{"a": {"generate": "x"}}, {"a": {"generate": "y"}}], "unique"),
    ([{"a": {"generate": "x"}}, {"o": {"output": "not a ref"}}], "needs a reference"),
    ([], "non-empty"),
])
def test_mistakes_are_named(steps, message):
    with pytest.raises(CompactError, match=message):
        expand(doc(steps))


def test_graf_expand_prints_the_long_form(tmp_path):
    path = tmp_path / "c.graph.yaml"
    YAML().dump(doc(CHAIN), path)
    result = CliRunner().invoke(main, ["expand", str(path)])
    assert result.exit_code == 0 and "nodes:" in result.output and "wf_entry.entry" in result.output
    assert "steps:" not in result.output


@pytest.mark.llm
def test_real_llm_runs_a_compact_graph(tmp_path):
    """claude_cli (claude-sonnet-5-5): two short calls."""
    steps = [{"a": {"generate": "Name one planet. Reply with the name only.", "out": "name"}},
             {"b": {"generate": "Reply with the number of letters in this word, digits only: {{in_name}}", "in": {"name": "a"}, "out": "n"}},
             {"done": {"output": "b"}}]
    out = GraphLangRuntime(expand(doc(steps, inputs=())), adapter="claude_cli", verbose=False).execute({})
    assert out["essay"].strip().isdigit()
