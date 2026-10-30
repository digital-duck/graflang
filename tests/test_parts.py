"""Named subgraphs (parts): a workflow file used as a node, checked against its interface, then expanded in place."""
import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from graphlang.grafr.parts import PartError
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check
from test_lifecycle import Scripted

DEMO = Path(__file__).parent.parent / "cookbook" / "parts_demo"
GRAPH = DEMO / "parts_demo.graph.yaml"


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump(data, path)
    return path


@pytest.fixture
def demo(tmp_path):
    dest = tmp_path / "parts_demo"
    shutil.copytree(DEMO, dest, ignore=shutil.ignore_patterns("output"))
    return dest


def test_a_part_used_twice_expands_to_two_independent_copies():
    graph = load_graph(GRAPH)
    ids = [n["id"] for n in graph["nodes"]]
    assert {"first__rewrite", "second__rewrite"} <= set(ids) and not any(n["type"] in ("SUBGRAPH",) for n in graph["nodes"])
    prompts = graph["resources"]["prompts"]
    assert set(prompts) >= {"first__rewrite", "second__rewrite"} and all(Path(p).is_absolute() and Path(p).exists() for p in prompts.values())
    assert check(graph) == ([], [])


def test_the_chain_runs_through_both_uses_with_the_right_tone_each_time():
    llm = Scripted("DRAFT", "FIRST", "SECOND")
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"topic": "tides"})
    assert out == {"essay": "SECOND"}
    assert "formal tone" in llm.prompts[1] and "DRAFT" in llm.prompts[1]
    assert "plain tone" in llm.prompts[2] and "FIRST" in llm.prompts[2]               # the part's own default for the second use


def test_the_long_form_subgraph_node_works_without_the_compact_syntax(demo):
    graph = {"version": "1.0-graph", "resources": {"parts": {"polish": "./parts/polish.graph.yaml"}},
             "workflow": {"name": "w", "inputs": [{"name": "text", "type": "TEXT"}], "outputs": [{"name": "out", "type": "TEXT"}]},
             "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_text"]},
                       {"id": "p", "type": "SUBGRAPH", "config": {"part": "parts.polish"}, "ports": ["trigger", "complete", "in_essay", "out_essay"]},
                       {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_out"]}],
             "edges": [{"source": "s.entry", "target": "p.trigger", "type": "triggers"}, {"source": "s.out_text", "target": "p.in_essay", "type": "binds"},
                       {"source": "p.complete", "target": "o.trigger", "type": "triggers"}, {"source": "p.out_essay", "target": "o.in_out", "type": "binds"}]}
    path = dump(demo / "w.graph.yaml", graph)
    loaded = load_graph(path)
    assert check(loaded) == ([], [])
    llm = Scripted("DONE")
    assert GraphLangRuntime(loaded, llm=llm, verbose=False).execute({"text": "hi"}) == {"out": "DONE"} and "plain tone" in llm.prompts[0]


def test_a_part_may_use_a_part(demo):
    outer = YAML().load((demo / "parts" / "polish.graph.yaml").read_text())
    outer["workflow"]["name"] = "twice"
    outer["resources"]["parts"] = {"polish": "./polish.graph.yaml"}
    outer["resources"].pop("prompts")
    outer["nodes"] = [outer["nodes"][0], {"id": "a", "type": "SUBGRAPH", "config": {"part": "parts.polish"}, "ports": ["trigger", "complete", "in_essay", "in_tone", "out_essay"]},
                      {"id": "b", "type": "SUBGRAPH", "config": {"part": "parts.polish"}, "ports": ["trigger", "complete", "in_essay", "out_essay"]},
                      outer["nodes"][2]]
    outer["edges"] = [{"source": "wf_entry.entry", "target": "a.trigger", "type": "triggers"}, {"source": "a.complete", "target": "b.trigger", "type": "triggers"},
                      {"source": "b.complete", "target": "wf_exit.trigger", "type": "triggers"},
                      {"source": "wf_entry.out_essay", "target": "a.in_essay", "type": "binds"}, {"source": "wf_entry.out_tone", "target": "a.in_tone", "type": "binds"},
                      {"source": "a.out_essay", "target": "b.in_essay", "type": "binds"}, {"source": "b.out_essay", "target": "wf_exit.in_essay", "type": "binds"}]
    dump(demo / "parts" / "twice.graph.yaml", outer)
    top = YAML().load(GRAPH.read_text())
    top["resources"]["parts"] = {"twice": "./parts/twice.graph.yaml"}
    top["steps"] = [{"t": {"use": "parts.twice", "in": {"essay": "hello", "tone": "calm"}, "out": ["essay"]}}, {"done": {"output": "t.essay"}}]
    top["workflow"]["inputs"] = []
    path = dump(demo / "nested.graph.yaml", top)
    graph = load_graph(path)
    assert {"t__a__rewrite", "t__b__rewrite"} <= {n["id"] for n in graph["nodes"]} and check(graph) == ([], [])
    llm = Scripted("ONE", "TWO")
    assert GraphLangRuntime(graph, llm=llm, verbose=False).execute({}) == {"essay": "TWO"}
    assert "calm tone" in llm.prompts[0]


def test_a_part_inside_a_loop_body_is_expanded_there(demo):
    graph = load_graph(GRAPH)
    base = {"version": "1.0-graph", "resources": {"parts": {"polish": "./parts/polish.graph.yaml"}},
            "workflow": {"name": "l", "inputs": [], "outputs": [{"name": "all", "type": "JSON"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry"]},
                      {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit", "out_all"],
                       "config": {"max_iterations": 2, "outputs": {"all": {"collect": "p__rewrite.out_essay"}},
                                  "subgraph": {"nodes": [{"id": "p", "type": "SUBGRAPH", "config": {"part": "parts.polish", "phases": {"pre": {"defaults": {"in_essay": "x"}}}},
                                                          "ports": ["trigger", "complete", "in_essay", "out_essay"]}], "edges": []}}},
                      {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_all"]}],
            "edges": [{"source": "s.entry", "target": "lp.trigger", "type": "triggers"}, {"source": "lp.out_all", "target": "o.in_all", "type": "binds"},
                      {"source": "lp.exit", "target": "o.trigger", "type": "triggers"}]}
    loaded = load_graph(dump(demo / "l.graph.yaml", base))
    body = loaded["nodes"][1]["config"]["subgraph"]["nodes"]
    assert [n["id"] for n in body] == ["p__rewrite"]
    assert GraphLangRuntime(loaded, llm=Scripted("A", "B"), verbose=False).execute({}) == {"all": ["A", "B"]}
    assert graph  # the demo itself still loads


@pytest.mark.parametrize("edit, message", [
    (lambda g: g["nodes"][1].__setitem__("ports", ["trigger", "complete", "in_essay", "in_mood", "out_essay"]), "in_mood is not an input"),
    (lambda g: g["nodes"][1].__setitem__("ports", ["trigger", "complete", "in_essay", "out_title"]), "out_title is not an output"),
    (lambda g: g["edges"].remove(next(e for e in g["edges"] if e["target"] == "p.in_essay")), "not bound and has no default"),
    (lambda g: g["nodes"][1]["config"].__setitem__("part", "parts.nope"), "not listed under resources.parts"),
    (lambda g: g["nodes"][1].__setitem__("ports", ["complete", "in_essay", "out_essay"]), "needs the ports trigger and complete"),
])
def test_a_use_that_does_not_match_the_interface_is_named(demo, edit, message):
    g = {"version": "1.0-graph", "resources": {"parts": {"polish": "./parts/polish.graph.yaml"}},
         "workflow": {"name": "w", "inputs": [{"name": "text", "type": "TEXT"}], "outputs": []},
         "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_text"]},
                   {"id": "p", "type": "SUBGRAPH", "config": {"part": "parts.polish"}, "ports": ["trigger", "complete", "in_essay", "out_essay"]}],
         "edges": [{"source": "s.entry", "target": "p.trigger", "type": "triggers"}, {"source": "s.out_text", "target": "p.in_essay", "type": "binds"}]}
    edit(g)
    with pytest.raises(PartError, match=message):
        load_graph(dump(demo / "bad.graph.yaml", g))


def test_a_part_that_uses_itself_is_refused(demo):
    part = YAML().load((demo / "parts" / "polish.graph.yaml").read_text())
    part["resources"]["parts"] = {"me": "./polish.graph.yaml"}
    part["nodes"].insert(1, {"id": "again", "type": "SUBGRAPH", "config": {"part": "parts.me"}, "ports": ["trigger", "complete", "in_essay", "out_essay"]})
    dump(demo / "parts" / "polish.graph.yaml", part)
    with pytest.raises(PartError, match="cannot use itself"):
        load_graph(GRAPH.parent.parent.joinpath(demo.name, "parts_demo.graph.yaml") if False else demo / "parts_demo.graph.yaml")


def test_a_part_without_an_input_node_is_refused(demo):
    part = YAML().load((demo / "parts" / "polish.graph.yaml").read_text())
    part["nodes"] = [n for n in part["nodes"] if n["type"] != "INPUT"]
    part["edges"] = [e for e in part["edges"] if not e["source"].startswith("wf_entry")]
    dump(demo / "parts" / "polish.graph.yaml", part)
    with pytest.raises(PartError, match="exactly one INPUT and one OUTPUT"):
        load_graph(demo / "parts_demo.graph.yaml")


def test_the_editor_checks_and_draws_a_file_that_uses_parts(demo):
    from graphlang.grafv.editor import GraphEditor
    g = YAML().load((demo / "parts_demo.graph.yaml").read_text())
    g.pop("steps")
    g["nodes"] = [{"id": "s", "type": "INPUT", "ports": ["entry", "out_topic"]},
                  {"id": "p", "type": "SUBGRAPH", "config": {"part": "parts.polish"}, "ports": ["trigger", "complete", "in_essay", "out_essay"]},
                  {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_essay"]}]
    g["edges"] = [{"source": "s.entry", "target": "p.trigger", "type": "triggers"}, {"source": "s.out_topic", "target": "p.in_essay", "type": "binds"},
                  {"source": "p.complete", "target": "o.trigger", "type": "triggers"}, {"source": "p.out_essay", "target": "o.in_essay", "type": "binds"}]
    path = dump(demo / "ed.graph.yaml", g)
    ed = GraphEditor(path)
    assert ed.problems()[0] == [] and ed.node_ids() == ["s", "p", "o"]                 # the editor sees the SUBGRAPH node, not its insides
    ed.set_config("p", "label", "polish it")
    ed.save()
    assert "polish it" in path.read_text()


@pytest.mark.llm
def test_real_llm_runs_the_demo():
    """claude_cli (claude-sonnet-5-5): three short calls, the part's prompt used twice."""
    out = GraphLangRuntime(load_graph(GRAPH), adapter="claude_cli", verbose=False).execute({"topic": "tides"})
    assert len(out["essay"].strip()) > 20
