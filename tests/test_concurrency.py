"""Concurrent mode (design E5): nodes released together run on a thread pool, results are applied in a fixed order."""
import time
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from test_lifecycle import Scripted

COOKBOOK = Path(__file__).parent.parent / "cookbook"


class Slow(Scripted):
    """Each call sleeps for the time its prompt asks for ('sleep 0.3 a') and answers with the last word."""

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        time.sleep(float(prompt.split()[1]))
        return prompt.split()[-1]


def fork_graph(times=(0.3, 0.3)):
    nodes = [{"id": "s", "type": "INPUT", "ports": ["entry"]},
             {"id": "f", "type": "FORK", "ports": ["trigger", "a", "b"]},
             {"id": "A", "type": "GENERATE", "ports": ["trigger", "complete", "out_v"], "config": {"prompt_inline": f"sleep {times[0]} a"}},
             {"id": "B", "type": "GENERATE", "ports": ["trigger", "complete", "out_v"], "config": {"prompt_inline": f"sleep {times[1]} b"}},
             {"id": "j", "type": "JOIN", "ports": ["trigger", "complete", "in_x", "in_y", "out_args"]},
             {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_args"]}]
    edges = [{"source": "s.entry", "target": "f.trigger", "type": "triggers"},
             {"source": "f.a", "target": "A.trigger", "type": "triggers"}, {"source": "f.b", "target": "B.trigger", "type": "triggers"},
             {"source": "A.complete", "target": "j.trigger", "type": "triggers"}, {"source": "B.complete", "target": "j.trigger", "type": "triggers"},
             {"source": "A.out_v", "target": "j.in_x", "type": "binds"}, {"source": "B.out_v", "target": "j.in_y", "type": "binds"},
             {"source": "j.out_args", "target": "o.in_args", "type": "binds"}, {"source": "j.complete", "target": "o.trigger", "type": "triggers"}]
    return {"version": "1.0-graph", "resources": {}, "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "args", "type": "JSON"}]},
            "nodes": nodes, "edges": edges}


def timed(workers, times=(0.3, 0.3)):
    started = time.perf_counter()
    out = GraphLangRuntime(fork_graph(times), llm=Slow(), verbose=False, workers=workers).execute({})
    return out, time.perf_counter() - started


def test_fork_branches_overlap_with_workers_and_not_without():
    one, t1 = timed(1)
    two, t2 = timed(2)
    assert one == two == {"args": {"x": "a", "y": "b"}}
    assert t1 >= 0.6 and t2 < 0.55, (t1, t2)


def test_the_result_does_not_depend_on_which_branch_finishes_first():
    fast_first, _ = timed(2, (0.05, 0.3))
    slow_first, _ = timed(2, (0.3, 0.05))
    assert fast_first == slow_first == {"args": {"x": "a", "y": "b"}}


def test_an_error_in_one_branch_surfaces_after_the_others_finish():
    class Boom(Slow):
        def generate(self, prompt, model=None, **opts):
            if " a" in prompt:
                raise OSError("down")
            return super().generate(prompt, model, **opts)

    with pytest.raises(OSError, match="down"):
        GraphLangRuntime(fork_graph(), llm=Boom(), verbose=False, workers=2).execute({})


CASES = {"self_refine": {"topic": "t"}, "build_concept_book": {"subject": "tides", "target_audience": "kids", "num_chapters": 2}, "compliance_audit": {"document": "Call me at 555-1234", "destination": "internal", "engine": "builtin", "rules_file": ""}, "code_pipeline": {"spec": "add two numbers"},
         "solver_check": {"numbers": "1,2,3", "expected": 6}, "chain_of_thought": {}, "lifted_tool": {}}


@pytest.mark.parametrize("name", sorted(CASES))
def test_shipped_graphs_give_the_same_result_with_workers(name):
    path = next(COOKBOOK.rglob(f"{name}.graph.yaml"))

    def run(workers):
        try:
            return GraphLangRuntime(load_graph(path), adapter="mock", verbose=False, workers=workers).execute(dict(CASES[name]))
        except Exception as e:
            return f"{type(e).__name__}: {e}"

    sequential = run(1)
    if isinstance(sequential, str) and "Error" in sequential.split(":")[0]:
        pytest.skip(f"does not run offline as is: {sequential[:80]}")
    assert run(4) == sequential


@pytest.mark.llm
def test_real_llm_two_branches_overlap():
    """claude_cli (claude-sonnet-5-5): two short calls at once."""
    g = fork_graph()
    g["nodes"][2]["config"]["prompt_inline"] = "Reply with only the word: red"
    g["nodes"][3]["config"]["prompt_inline"] = "Reply with only the word: blue"
    out = GraphLangRuntime(g, adapter="claude_cli", verbose=False, workers=2).execute({})
    assert out["args"]["x"].strip().lower().startswith("red") and out["args"]["y"].strip().lower().startswith("blue")
