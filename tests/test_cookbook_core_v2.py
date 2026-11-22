"""cookbook_v2, the core recipes that were already written in the compact form (they were copied, with their paths and error catalogue fixed): each one must validate,
and run next to its original in cookbook/ on the mock adapter, from its own folder, it must give the same outputs (or fail the same way)."""
import re
from pathlib import Path

import pytest

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
V2, ORIGINALS = ROOT / "cookbook_v2", ROOT / "cookbook"
NAMES = ["assembler", "chain_of_thought", "code_parts", "container_demo", "doc_it", "expand_demo", "guardrail", "hello_world", "lifted_tool", "parts_demo",
         "recipe_chain", "release_approval", "solver_check", "stock_analysis", "pocketflow/debate", "pocketflow/majority_vote", "pocketflow/text_transformer"]


def graph(base, name):
    folder, _, stem = name.partition("/")              # "stock_analysis", or "pocketflow/debate" for a folder of several graphs
    return base / folder / f"{stem or folder}.graph.yaml"


def scrub(value):
    text = str(value)
    text = re.sub(r"\b\d+(?:\.\d+)?\s?(?:ms|sec|seconds|s)\b", "N s", text)
    text = re.sub(r"(?i)((?:elapsed|time|latency)[^\n\d]{0,14})\d+(?:\.\d+)?", r"\1N", text)
    text = re.sub(r"('hostname': ')\w+", r"\1HOST", text)                # a container's hostname is random
    text = re.sub(r"/tmp/tmp\w+", "/tmp/TMP", text)
    text = re.sub(r"node '[^']*'", "node 'N'", text)
    text = re.sub(r"(\d\.\d{3})\d+", r"\1", text)
    text = re.sub(r"\d{4}-\d\d-\d\d[_ T]\d\d[-:]\d\d[-:]\d\d", "TIMESTAMP", text)
    text = re.sub(r"cookbook(?:_v2)?/", "RECIPES/", text)
    return re.sub(r"procedures\.(?:\w+?__)?\w*", "procedures.P", text)


@pytest.mark.parametrize("name", NAMES)
def test_the_copy_validates_with_no_errors_and_no_new_warnings(name):
    errors, warnings = check(load_graph(graph(V2, name)))
    _, original = check(load_graph(graph(ORIGINALS, name)))
    assert errors == [] and len(warnings) <= len(original), warnings


@pytest.mark.parametrize("name", NAMES)
def test_the_copy_gives_the_original_s_outputs(name, monkeypatch):
    def run(base):
        monkeypatch.chdir(base / name.split("/")[0])
        g = load_graph(graph(base, name))
        rt = GraphLangRuntime(g, llm=make_llm("mock", None), verbose=False)
        try:
            return scrub(rt.execute({}))
        except Exception as e:                      # noqa: BLE001
            return f"{type(e).__name__}: {scrub(e)}"
    assert run(V2) == run(ORIGINALS)
