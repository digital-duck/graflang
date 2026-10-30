"""A graph lifted from an SPL workflow (cookbook/chain_of_thought, made by SPL.py's spl2graph) runs like any other."""
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph

GRAPH = Path(__file__).parent.parent / "cookbook" / "chain_of_thought" / "chain_of_thought.graph.yaml"


class Echo:
    name, model_override = "echo", None

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return f"R{len(self.prompts)}"


def test_each_step_sees_the_previous_answer_and_the_input_default_applies():
    llm = Echo()
    assert GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({}) == {"summary": "R3"}
    assert llm.prompts[0] == "Research and provide key facts about distributed AI inference."
    assert "Research: R1" in llm.prompts[1] and "Analysis: R2" in llm.prompts[2]


def test_a_literal_argument_is_a_port_default():
    graph = load_graph(GRAPH)
    graph["nodes"][1]["config"]["phases"] = {"pre": {"defaults": {"in_topic": "tides"}}}
    graph["edges"] = [e for e in graph["edges"] if e["target"] != "gen_1.in_topic"]
    llm = Echo()
    GraphLangRuntime(graph, llm=llm, verbose=False).execute({})
    assert llm.prompts[0] == "Research and provide key facts about tides."


@pytest.mark.llm
def test_real_llm_runs_the_lifted_chain():
    """claude_cli (claude-sonnet-5-5): three short calls."""
    out = GraphLangRuntime(load_graph(GRAPH), adapter="claude_cli", verbose=False).execute({"topic": "a tide"})
    assert len(out["summary"].strip()) > 20
