"""cookbook_solvers_v2: the lifted solver recipes in the layered form (scripts/port_solver.py). Each one must validate with no errors and no more warnings than its original and,
run next to its original in cookbook_solvers/ on the mock adapter, give the same outputs with the solver switch on and off (the tools really run, in
a Jupyter kernel; the model answers with the mock's placeholder text, which names the prompt it was asked, so equal outputs mean equal prompts)."""
import re
from pathlib import Path

import pytest

pytest.importorskip("jupyter_client", reason="the tools of these recipes run in a Jupyter kernel (the `kernel` extra)")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
V2, ORIGINALS = ROOT / "cookbook_solvers_v2", ROOT / "cookbook_solvers"
GRAPHS = sorted(f"{g.parent.name}/{g.name.removesuffix('.graph.yaml')}" for g in V2.glob("*/*.graph.yaml"))      # every graph of every recipe: a recipe may hold several, named as they like
NAMES = GRAPHS


def path(base, name):
    folder, graph = name.split("/")
    return base / folder / f"{graph}.graph.yaml"


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_validates_with_no_errors_and_no_new_warnings(name):
    """No errors, and no warning its original does not have too (a few lifted loops read an input from the loop's state, which the checker warns about)."""
    errors, warnings = check(load_graph(path(V2, name)))
    _, original = check(load_graph(path(ORIGINALS, name)))
    assert errors == [] and len(warnings) <= len(original), warnings


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_reads_as_a_few_composites(name):
    from graphlang.grafv.model import build
    top, _ = build(load_graph(path(V2, name)), 0)
    assert top.number_of_nodes() <= 10, f"{top.number_of_nodes()} boxes at the top level"


def scrub(value):
    """What differs from run to run, or by where the recipe lives: a solver's solve time, a temporary file name, a timestamp, the recipe's folder, and the part a
    procedure moved into (a mock procedure names itself, `procedures.drafts__gen_tests` after `graf group`)."""
    text = str(value)
    text = re.sub(r"(?i)((?:solve|elapsed|wall|cpu|run)?[ _]?time[^\n\d]{0,14})\d+(?:\.\d+)?", r"\1N", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s?(?:ms|sec|seconds|s)\b", "N s", text)        # any duration: "1.7s", "0.32 s", "in 2 seconds"
    text = re.sub(r"(\b\w*_s\b[\"']?\s*[:=]\s*)-?\d+(?:\.\d+)?", r"\1N", text)           # a metric whose unit is in its name: "stage1_s": 0.012
    text = re.sub(r"(\(s\) \| )-?\d+(?:\.\d+)?", r"\1N", text)                       # a report's timing row: "Total latency (s) | 0.20"
    text = re.sub(r"/tmp/tmp\w+", "/tmp/TMP", text)
    text = re.sub(r"node '[^']*'", "node 'N'", text)                # the node id in an error message
    text = re.sub(r"(\d\.\d{3})\d+", r"\1", text)                      # a numerical solver or a live market feed differs in the last digits
    text = re.sub(r"\d{4}-\d\d-\d\d[_ T]\d\d[-:]\d\d[-:]\d\d", "TIMESTAMP", text)
    text = re.sub(r"cookbook_solvers(?:_v2)?/", "RECIPES/", text)
    return re.sub(r"procedures\.(?:\w+?__)?\w*", "procedures.P", text)       # a mock procedure's name, cut at a fixed width and longer by the part's prefix


def settings(graph, on):
    """The inputs of a run: the solver switch set, or none when the recipe has no switch (it runs on its defaults)."""
    names = [i["name"] for i in graph["workflow"]["inputs"] if "solver" in i["name"]]
    return {names[0]: on} if len(names) == 1 else {}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("on", ["true", "false"])
def test_the_layered_recipe_gives_the_original_s_outputs(name, on, monkeypatch):
    """Each run starts in its recipe's folder (a recipe reads `rules.json` and the like relative to it). A run that cannot finish on the mock must fail the same way in both."""
    def run(base):
        monkeypatch.chdir(base / name.split("/")[0])
        g = load_graph(path(base, name))
        rt = GraphLangRuntime(g, llm=make_llm("mock", None), verbose=False)
        try:
            return scrub(rt.execute(settings(g, on)))
        except Exception as e:                      # noqa: BLE001
            return f"{type(e).__name__}: {scrub(e)}"
    assert run(V2) == run(ORIGINALS)
