"""Elaboration: a part applied to every node of a graph of things, edges becoming order and data."""
import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from graphlang.grafr.parts import PartError
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

DEMO = Path(__file__).parent.parent / "cookbook" / "elaborate_demo"
GRAPH = DEMO / "elaborate_demo.graph.yaml"


class Echo:
    """Answers each prompt with `ANSWER(<concept>)` and keeps the prompts."""
    name = "echo"
    model_override = None

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return "ANSWER(" + prompt.split('"')[1] + ")"


@pytest.fixture
def demo(tmp_path):
    dest = tmp_path / "e"
    shutil.copytree(DEMO, dest, ignore=shutil.ignore_patterns("output"))
    return dest


def edit(demo, **changes):
    data = YAML(typ="safe").load((demo / "elaborate_demo.graph.yaml").read_text())
    for key, value in changes.items():
        data["elaborate"][key] = value
    out = demo / "x.graph.yaml"
    YAML().dump(data, out)
    return out


def test_one_use_per_thing_with_a_fork_at_the_roots_and_a_join_where_edges_meet():
    g = load_graph(GRAPH)
    ids = {n["id"] for n in g["nodes"]}
    assert {"probability__write", "counting__write", "entropy__write", "coding__write", "elab_start", "elab_in_entropy", "elab_done"} <= ids
    assert "elab_in_coding" not in ids and "elab_in_probability" not in ids               # one predecessor: a plain wire
    assert check(g) == ([], [])


@pytest.mark.parametrize("workers", [1, 2])
def test_each_thing_waits_for_its_prerequisites_and_sees_what_they_wrote(workers):
    llm = Echo()
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, workers=workers, verbose=False).execute({})
    assert out["explanations"] == {k: f"ANSWER({v})" for k, v in
                                   {"counting": "counting outcomes", "probability": "probability", "entropy": "Shannon entropy", "coding": "optimal coding"}.items()}
    by_concept = {p.split('"')[1]: p for p in llm.prompts}
    assert "'probability': 'ANSWER(probability)'" in by_concept["Shannon entropy"] and "'counting': 'ANSWER(counting outcomes)'" in by_concept["Shannon entropy"]
    assert "ANSWER(Shannon entropy)" in by_concept["optimal coding"]
    assert llm.prompts.index(by_concept["Shannon entropy"]) > llm.prompts.index(by_concept["probability"])
    assert llm.prompts.index(by_concept["optimal coding"]) == 3                           # last: it comes after entropy
    assert "curious beginners" in by_concept["probability"]                               # the shared workflow input


def test_a_graph_given_inline_with_one_root_has_no_fork(demo):
    path = edit(demo, over={"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}], "edges": [{"source": "a", "target": "b"}]})
    g = load_graph(path)
    assert "elab_start" not in {n["id"] for n in g["nodes"]}
    llm = Echo()
    assert GraphLangRuntime(g, llm=llm, verbose=False).execute({})["explanations"] == {"a": "ANSWER(A)", "b": "ANSWER(B)"}


def test_without_pass_there_is_only_ordering(demo):
    path = edit(demo, over={"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}], "edges": [{"source": "a", "target": "b"}]})
    data = YAML(typ="safe").load(path.read_text())
    del data["elaborate"]["pass"]
    YAML().dump(data, path)
    llm = Echo()
    GraphLangRuntime(load_graph(path), llm=llm, verbose=False).execute({})
    assert "ANSWER(A)" not in llm.prompts[1] and "{}" in llm.prompts[1]


@pytest.mark.parametrize("changes, message", [
    ({"over": {"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}], "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]}}, "has a cycle"),
    ({"over": {"nodes": [{"id": "a"}]}}, "no attribute 'title'"),
    ({"over": {"nodes": [{"id": "a", "title": "A"}], "edges": [{"source": "a", "target": "zz"}]}}, "unknown node"),
    ({"over": {"nodes": [{"id": "a b", "title": "A"}]}}, "letters, digits"),
    ({"over": {"nodes": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]}}, "duplicate"),
    ({"part": "parts.nope"}, "not listed under resources.parts"),
    ({"with": {"nope": "title"}}, "not an input of the part"),
    ({"shared": ["concept"]}, "not a workflow input"),
    ({"result": "nope"}, "not an output of the part"),
    ({"pass": {"from": "nope", "to": "context"}}, "not an output of the part"),
    ({"over": "./missing.yaml"}, "not found"),
])
def test_a_bad_elaboration_is_named(demo, changes, message):
    with pytest.raises(PartError, match=message):
        load_graph(edit(demo, **changes))


@pytest.mark.llm
def test_real_llm_explains_a_small_graph(demo):
    path = edit(demo, over={"nodes": [{"id": "p", "title": "probability"}, {"id": "e", "title": "entropy"}], "edges": [{"source": "p", "target": "e"}]})
    out = GraphLangRuntime(load_graph(path), adapter="claude_cli", verbose=False).execute({})
    assert set(out["explanations"]) == {"p", "e"} and all(len(v) > 20 for v in out["explanations"].values())
