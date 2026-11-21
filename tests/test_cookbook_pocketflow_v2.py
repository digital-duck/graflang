"""cookbook_pocketflow_v2: PocketFlow recipes in the layered form (scripts/port_recipe.py, groups chosen per recipe). Each must validate with no errors or
warnings and, run next to its original in cookbook_pocketflow/ with its default inputs on the mock adapter, give the same outputs (the tools really run;
the mock's placeholder answer names the prompt it was asked, so equal outputs mean equal prompts)."""
import re
from pathlib import Path

import pytest

pytest.importorskip("jupyter_client", reason="the tools of these recipes run in a Jupyter kernel (the `kernel` extra)")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
V2, ORIGINALS = ROOT / "cookbook_pocketflow_v2", ROOT / "cookbook_pocketflow"
NAMES = sorted(d.name for d in V2.iterdir() if d.is_dir() and list(d.glob("*.graph.yaml")))


def graph(base, name):
    (g,) = (base / name).glob("*.graph.yaml")
    return g


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_validates_with_no_errors_and_no_warnings(name):
    assert check(load_graph(graph(V2, name))) == ([], [])


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_has_composites_and_a_short_top_level(name):
    from graphlang.grafv.model import build
    top, _ = build(load_graph(graph(V2, name)), 0)
    assert top.number_of_nodes() <= 14, f"{top.number_of_nodes()} boxes at the top level"
    assert any(p.is_dir() and list(p.glob("*.graph.yaml")) for p in (V2 / name).iterdir()), "no composite"


def scrub(value):
    """What differs from run to run or by where a step lives: a temporary file name, the node id in an error message, and the part a mock procedure moved into
    (`procedures.translate__translate_and_save` after `graf group`)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    text = re.sub(r"/tmp/tmp\w+", "/tmp/TMP", str(value))
    text = re.sub(r"node '[^']*'", "node 'N'", text)
    text = re.sub(r"procedures\.\w+?__", "procedures.", text)
    # a mock procedure lists its inputs in port order, and grouping changes the order of the ports: compare them as a set
    return re.sub(r"(\[Mock procedure [\w.]+\] )(.*?)(?=\n\[Mock procedure|\Z)",
                  lambda m: m.group(1) + ", ".join(sorted(re.split(r", (?=in_\w+=)", m.group(2)))), text, flags=re.S)


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_gives_the_original_s_outputs(name):
    """With its default inputs on the mock adapter. A recipe that cannot finish there (it needs a server, or a real answer to name a file) must fail the same way in both."""
    def run(base):
        rt = GraphLangRuntime(load_graph(graph(base, name)), llm=make_llm("mock", None), verbose=False)
        try:
            return scrub(rt.execute({}))
        except Exception as e:                      # noqa: BLE001
            return f"{type(e).__name__}: {scrub(e)}"
    assert run(V2) == run(ORIGINALS)
