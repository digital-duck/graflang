"""cookbook_solvers_v2: the lifted solver recipes in the layered form (scripts/port_solver.py). Each one must validate with no errors or warnings and,
run next to its original in cookbook_solvers/ on the mock adapter, give the same outputs with the solver switch on and off (the tools really run, in
a Jupyter kernel; the model answers with the mock's placeholder text, which names the prompt it was asked, so equal outputs mean equal prompts)."""
from pathlib import Path

import pytest

pytest.importorskip("jupyter_client", reason="the tools of these recipes run in a Jupyter kernel (the `kernel` extra)")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
V2, ORIGINALS = ROOT / "cookbook_solvers_v2", ROOT / "cookbook_solvers"
NAMES = sorted(d.name for d in V2.iterdir() if d.is_dir() and (d / f"{d.name}.graph.yaml").exists())


def path(base, name):
    return base / name / f"{name}.graph.yaml"


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_validates_with_no_errors_and_no_warnings(name):
    assert check(load_graph(path(V2, name))) == ([], [])


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_reads_as_a_few_composites(name):
    from graphlang.grafv.model import build
    top, _ = build(load_graph(path(V2, name)), 0)
    assert top.number_of_nodes() <= 10, f"{top.number_of_nodes()} boxes at the top level"


def switch(graph):
    (name,) = [i["name"] for i in graph["workflow"]["inputs"] if "solver" in i["name"]]
    return name


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("on", ["true", "false"])
def test_the_layered_recipe_gives_the_original_s_outputs(name, on):
    def run(base):
        g = load_graph(path(base, name))
        rt = GraphLangRuntime(g, llm=make_llm("mock", None), verbose=False)
        return rt.execute({switch(g): on})
    assert run(V2) == run(ORIGINALS)
