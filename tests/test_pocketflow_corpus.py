"""R1 acceptance corpus (design E1): the PocketFlow-derived recipes in SPL.py/cookbook-pocketflow.

* every recipe lifts to a graph that passes `graf validate` (needs SPL.py and its cookbook; skipped without them);
* three lifted samples are kept in cookbook/pocketflow and run here with no SPL.py and no model: a deterministic one, and
  two LLM ones replayed from cassettes recorded with claude_cli (claude-sonnet-5-5)."""
import os
import tempfile
from pathlib import Path

import pytest

from graphlang.grafr.metering import MeteredLLM, ReplayLLM
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

SAMPLES = Path(__file__).parent.parent / "cookbook" / "pocketflow"
CORPUS = Path(os.environ.get("SPL_PY_PATH", Path(__file__).parent.parent.parent / "SPL.py")) / "cookbook-pocketflow"
RECIPES = sorted(p for p in CORPUS.rglob("*.spl") if p.is_file() and "generated" not in p.parts and "logs" not in p.parts) if CORPUS.is_dir() else []
HELPERS = {"tools.spl"}                                   # tool definitions shared by a recipe, not workflows


@pytest.mark.parametrize("path", RECIPES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_recipe_lifts_and_validates(path):
    spl2graph = pytest.importorskip("spl3.spl2graph")
    if path.name in HELPERS:
        with pytest.raises(spl2graph.NoWorkflowError):
            spl2graph.spl_to_graph(path.read_text(), source_name=path.name, source_dir=path.parent)
        return
    graph, _ = spl2graph.spl_to_graph(path.read_text(), source_name=path.name, source_dir=path.parent)
    out = Path(tempfile.mkdtemp()) / "g.graph.yaml"
    out.write_text(spl2graph.graph_to_yaml(graph))
    loaded = load_graph(out)
    loaded["_source_dir"] = str(path.parent)               # procedures and tools are found next to the recipe
    errors, _ = check(loaded)
    assert errors == []


def test_the_corpus_is_there_when_spl_py_is():
    pytest.importorskip("spl3.spl2graph")
    if not CORPUS.is_dir():
        pytest.skip("SPL.py has no cookbook-pocketflow here")
    assert len(RECIPES) >= 80                              # 83 workflows and 4 tool files when this was written


@pytest.mark.parametrize("name", ["majority_vote", "debate", "text_transformer"])
def test_the_kept_samples_validate(name):
    assert check(load_graph(SAMPLES / f"{name}.graph.yaml")) == ([], [])


def test_text_transformer_runs_its_five_commands_with_no_model():
    rt = GraphLangRuntime(load_graph(SAMPLES / "text_transformer.graph.yaml"), verbose=False)
    log = rt.execute({})["session_log"]
    for line in ("[uppercase] 'hello world' => 'HELLO WORLD'", "[lowercase] 'HELLO WORLD' => 'hello world'", "[reverse] 'abcdef' => 'fedcba'",
                 "[collapse whitespace] 'hello   world   foo' => 'hello world foo'", "[exit] Session ended."):
        assert line in log
    # the recipe counts from 0 but its list_get is 1-based, so the first round reads an empty command (as it does in SPL itself)
    assert log.startswith("=== Text Transformation Tool ===") and "[] '' => ''" in log
    assert log.count("=== Text Transformation Tool ===") == 6 and log.rstrip().endswith("[exit] Session ended.")


def test_majority_vote_replays_three_samples_and_a_vote():
    llm = MeteredLLM(ReplayLLM(SAMPLES / "majority_vote.cassette.jsonl"))
    rt = GraphLangRuntime(load_graph(SAMPLES / "majority_vote.graph.yaml"), llm=llm, verbose=False)
    assert rt.execute({}) == {"answer": "36"}                    # 15% of 240
    assert rt.summary()["llm"]["calls"] == 3


def test_debate_replays_two_rounds_to_a_verdict():
    llm = MeteredLLM(ReplayLLM(SAMPLES / "debate.cassette.jsonl"))
    rt = GraphLangRuntime(load_graph(SAMPLES / "debate.graph.yaml"), llm=llm, verbose=False)
    out = rt.execute({"max_iterations": 2})
    assert rt.summary()["llm"]["calls"] == 11 and "verdict" in out["result"].lower() and len(out["result"]) > 300
