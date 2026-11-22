"""cookbook_pocketflow_v2: PocketFlow recipes in the layered form (or, when nothing groups, flat with named steps) (scripts/port_recipe.py, groups chosen per recipe). Each must validate with no errors or
warnings and, run next to its original in cookbook_pocketflow/ with its default inputs on the mock adapter, give the same outputs (the tools really run;
the mock's placeholder answer names the prompt it was asked, so equal outputs mean equal prompts)."""
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("jupyter_client", reason="the tools of these recipes run in a Jupyter kernel (the `kernel` extra)")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
V2, ORIGINALS = ROOT / "cookbook_pocketflow_v2", ROOT / "cookbook_pocketflow"
FLAT = {d.name for d in (ROOT / "cookbook_pocketflow_v2").iterdir() if d.is_dir() and list(d.glob("*.graph.yaml")) and not any(c.is_dir() and list(c.glob("*.graph.yaml")) for c in d.iterdir())}   # ported with named steps, no composite (nothing to group)
NAMES = sorted(d.name for d in V2.iterdir() if d.is_dir() and list(d.glob("*.graph.yaml")))


def graph(base, name):
    named = base / name / f"{name}.graph.yaml"                # a recipe with two graphs (chat: the loop and one turn) is tested through the one named after it
    if named.exists():
        return named
    (g,) = (base / name).glob("*.graph.yaml")
    return g


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_validates_with_no_errors_and_no_warnings(name):
    assert check(load_graph(graph(V2, name))) == ([], [])


@pytest.mark.parametrize("name", NAMES)
def test_the_layered_recipe_has_composites_and_a_short_top_level_or_is_listed_as_flat(name):
    from graphlang.grafv.model import build
    top, _ = build(load_graph(graph(V2, name)), 0)
    has_composite = any(p.is_dir() and list(p.glob("*.graph.yaml")) for p in (V2 / name).iterdir())
    if name in FLAT:
        assert not has_composite
        return
    assert top.number_of_nodes() <= 14, f"{top.number_of_nodes()} boxes at the top level"
    assert has_composite, "no composite"


def scrub(value):
    """What differs from run to run or by where a step lives: a temporary file name, the node id in an error message, and the part a mock procedure moved into
    (`procedures.translate__translate_and_save` after `graf group`)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str) and value.lstrip()[:1] in "{[":           # a value that is itself JSON (a tool's result): its parts are compared one by one
        try:
            return scrub(json.loads(value))
        except ValueError:
            pass
    text = re.sub(r"/tmp/tmp\w+", "/tmp/TMP", str(value))
    text = re.sub(r"node '[^']*'", "node 'N'", text)
    text = re.sub(r"\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d", "TIMESTAMP", text)        # a clock read by a tool
    text = re.sub(r"-?\d+\.\d{6,}", "FLOAT", text)                                  # a random embedding differs in every run, even of the original
    text = re.sub(r"pocketflow_\d{10,}", "pocketflow_ID", text)                   # an id made from the clock
    text = re.sub(r"procedures\.\w+?__", "procedures.", text)
    # a mock procedure lists its inputs in port order, and grouping changes the order of the ports: compare them as a set
    text = re.sub(r"(\[Mock procedure [\w.]+\] )(.*?)(?=\n\[Mock procedure|\Z)",
                  lambda m: m.group(1) + ", ".join(sorted(re.split(r", (?=in_\w+=)", m.group(2)))), text, flags=re.S)
    return text


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
