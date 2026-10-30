"""Checkpoint and resume (design E9): a failed run continues from the last step instead of starting over."""
import json

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.runtime import GraphLangRuntime
from test_concurrency import fork_graph
from test_lifecycle import Scripted

CHAIN = {"version": "1.0-graph", "resources": {},
         "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "c", "type": "TEXT"}]},
         "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry"]},
                   *[{"id": i, "type": "GENERATE", "ports": ["trigger", "complete", "in_prev", "out_v"], "config": {"prompt_inline": f"{i} {{{{in_prev}}}}"}}
                     for i in "abc"],
                   {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_c"]}],
         "edges": [{"source": "s.entry", "target": "a.trigger", "type": "triggers"},
                   {"source": "a.complete", "target": "b.trigger", "type": "triggers"},
                   {"source": "b.complete", "target": "c.trigger", "type": "triggers"},
                   {"source": "c.complete", "target": "o.trigger", "type": "triggers"},
                   {"source": "a.out_v", "target": "b.in_prev", "type": "binds"},
                   {"source": "b.out_v", "target": "c.in_prev", "type": "binds"},
                   {"source": "c.out_v", "target": "o.in_c", "type": "binds"}]}


def test_a_failed_run_resumes_at_the_failed_step(tmp_path):
    ckpt = tmp_path / "run.ckpt.json"
    flaky = Scripted("A", OSError("model down"))
    rt = GraphLangRuntime(CHAIN, llm=flaky, verbose=False)
    rt.checkpoint_path = ckpt
    with pytest.raises(OSError):
        rt.execute({})
    assert json.loads(ckpt.read_text())["queue"] == [["b", ["a", 0]]]            # b was next when the run stopped

    healthy = Scripted("B", "C")
    again = GraphLangRuntime(CHAIN, llm=healthy, verbose=False)
    out = again.resume(ckpt)
    assert out == {"c": "C"} and healthy.prompts == ["b A", "c B"]               # a was not run again; b saw a's answer
    assert again.fired == {"s": 1, "a": 1, "b": 1, "c": 1, "o": 1}                 # a fired once, in the first run


def test_a_join_waiting_for_a_branch_survives_the_resume(tmp_path):
    ckpt = tmp_path / "fork.ckpt.json"

    class FailsOnB(Scripted):
        def generate(self, prompt, model=None, **opts):
            if " b" in prompt and not getattr(self, "healed", False):
                raise OSError("b down")
            return prompt.split()[-1]

    llm = FailsOnB()
    rt = GraphLangRuntime(fork_graph((0.0, 0.0)), llm=llm, verbose=False)
    rt.checkpoint_path = ckpt
    with pytest.raises(OSError):
        rt.execute({})
    llm.healed = True
    out = GraphLangRuntime(fork_graph((0.0, 0.0)), llm=llm, verbose=False).resume(ckpt)
    assert out == {"args": {"x": "a", "y": "b"}}


def test_a_checkpoint_from_another_graph_is_refused(tmp_path):
    ckpt = tmp_path / "c.json"
    rt = GraphLangRuntime(CHAIN, llm=Scripted("A", OSError("x")), verbose=False)
    rt.checkpoint_path = ckpt
    with pytest.raises(OSError):
        rt.execute({})
    other = json.loads(json.dumps(CHAIN))
    other["nodes"][1]["config"]["prompt_inline"] = "changed"
    with pytest.raises(ValueError, match="different graph"):
        GraphLangRuntime(other, llm=Scripted(), verbose=False).resume(ckpt)
    (tmp_path / "junk.json").write_text("{}")
    with pytest.raises(ValueError, match="not a graflang checkpoint"):
        GraphLangRuntime(CHAIN, llm=Scripted(), verbose=False).resume(tmp_path / "junk.json")


def test_a_value_that_is_not_json_turns_checkpointing_off_without_failing_the_run(tmp_path):
    class Odd(Scripted):
        def generate(self, prompt, model=None, **opts):
            return {1, 2}                                  # a set is not JSON

    ckpt = tmp_path / "c.json"
    rt = GraphLangRuntime(CHAIN, llm=Odd(), verbose=False)
    rt.checkpoint_path = ckpt
    rt.execute({})
    assert rt.outputs["c"] == {1, 2}


def test_graf_run_checkpoints_and_resumes(tmp_path):
    from ruamel.yaml import YAML
    graph = tmp_path / "w.graph.yaml"
    YAML().dump(CHAIN, graph)
    ckpt = tmp_path / "w.ckpt.json"
    bad = tmp_path / "bad.jsonl"
    # a replay cassette with only the first call: the second call fails, leaving a checkpoint at step b
    from graphlang.grafr.metering import RecordingLLM
    RecordingLLM(Scripted("A"), bad).generate("a ", model="claude-sonnet-5-5")
    first = CliRunner().invoke(main, ["run", str(graph), "--replay", str(bad), "--checkpoint", str(ckpt), "--no-log", "--no-output"])
    assert first.exit_code != 0 and ckpt.exists()
    second = CliRunner().invoke(main, ["run", str(graph), "--adapter", "mock", "--resume", str(ckpt), "--no-log", "--no-output"])
    assert second.exit_code == 0 and "Workflow completed" in second.output
