"""Bindings (design E6): a graph names logical things, a bindings file says which model, files and limits to use."""
import time

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from graphlang.cli import main
from graphlang.grafr.bindings import bind_graph, load_bindings
from graphlang.grafr.runtime import GraphLangRuntime, RunLimitExceeded

from test_lifecycle import Scripted


def write(path, data):
    YAML().dump(data, path)
    return path


def graph(model="$fast", prompts=None):
    node = {"id": "g", "type": "GENERATE", "ports": ["trigger", "complete", "out_text"],
            "config": {"prompt_inline": "hi", "model": model} if not prompts else {"prompt_ref": "prompts.p", "model": model}}
    return {"version": "1.0-graph", "resources": {"prompts": prompts} if prompts else {},
            "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "text", "type": "TEXT"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry"]}, node,
                      {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_text"]}],
            "edges": [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
                      {"source": "g.out_text", "target": "o.in_text", "type": "binds"},
                      {"source": "g.complete", "target": "o.trigger", "type": "triggers"}]}


class Spy(Scripted):
    def generate(self, prompt, model=None, **opts):
        self.models = getattr(self, "models", []) + [model]
        return super().generate(prompt, model, **opts)


def test_a_logical_model_becomes_the_bound_one_and_an_unbound_one_falls_back(tmp_path):
    bound, notes = bind_graph(graph(), {"models": {"fast": "claude-haiku-5-5"}})
    assert bound["nodes"][1]["config"]["model"] == "claude-haiku-5-5" and notes == []
    unbound, notes = bind_graph(graph(), {})
    assert "model" not in unbound["nodes"][1]["config"] and "no binding" in notes[0]
    assert graph()["nodes"][1]["config"]["model"] == "$fast"                        # the original is untouched
    kept, _ = bind_graph(graph("ollama/gemma3"), {"models": {"fast": "x"}})
    assert kept["nodes"][1]["config"]["model"] == "ollama/gemma3"                    # a concrete hint stays


def test_the_bound_model_reaches_the_llm_call():
    bound, _ = bind_graph(graph(), {"models": {"fast": "claude-haiku-5-5"}})
    llm = Spy("ok")
    GraphLangRuntime(bound, llm=llm, verbose=False).execute({})
    assert llm.models == ["claude-haiku-5-5"]


def test_models_inside_a_loop_body_are_bound_too():
    body = {"nodes": [{"id": "i", "type": "GENERATE", "ports": ["trigger"], "config": {"prompt_inline": "x", "model": "$fast"}}], "edges": []}
    g = graph()
    g["nodes"].append({"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"subgraph": body, "max_iterations": 1}})
    bound, _ = bind_graph(g, {"models": {"fast": "m"}})
    assert bound["nodes"][-1]["config"]["subgraph"]["nodes"][0]["config"]["model"] == "m"


def test_resources_are_replaced_relative_to_the_bindings_file(tmp_path):
    (tmp_path / "prod").mkdir()
    (tmp_path / "prod" / "p.md").write_text("PROD PROMPT")
    (tmp_path / "dev.md").write_text("DEV PROMPT")
    g = graph("m", prompts={"p": str(tmp_path / "dev.md")})
    g["_source_dir"] = str(tmp_path)
    b = load_bindings(write(tmp_path / "prod.bind.yaml", {"resources": {"prompts": {"p": "./prod/p.md"}}}))
    bound, notes = bind_graph(g, b)
    llm = Scripted("ok")
    GraphLangRuntime(bound, llm=llm, verbose=False).execute({})
    assert llm.prompts == ["PROD PROMPT"] and notes == []
    _, notes = bind_graph(g, load_bindings(write(tmp_path / "x.bind.yaml", {"resources": {"prompts": {"nope": "./a.md"}}})))
    assert "no prompt 'nope'" in notes[0]


@pytest.mark.parametrize("data, message", [
    ({"typo": 1}, "unknown key"),
    ({"limits": {"max_cost": 5}}, "max_cost is not supported"),
    ({"limits": {"max_steps": 0}}, "must be a number > 0"),
    ({"limits": {"nope": 1}}, "unknown limit"),
    ({"resources": {"weights": {"a": "b"}}}, "resources.weights"),
    ({"models": ["fast"]}, "models must be a mapping"),
])
def test_a_bad_bindings_file_is_named(tmp_path, data, message):
    with pytest.raises(ValueError, match=message):
        load_bindings(write(tmp_path / "b.yaml", data))


def test_wall_time_stops_a_run():
    class Slow(Scripted):
        def generate(self, prompt, model=None, **opts):
            time.sleep(0.3)
            return "x"

    g = graph("m")
    g["nodes"].insert(2, {"id": "g2", "type": "GENERATE", "ports": ["trigger", "complete", "out_text"], "config": {"prompt_inline": "y"}})
    g["edges"] = [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
                  {"source": "g.complete", "target": "g2.trigger", "type": "triggers"},
                  {"source": "g2.out_text", "target": "o.in_text", "type": "binds"},
                  {"source": "g2.complete", "target": "o.trigger", "type": "triggers"}]
    with pytest.raises(RunLimitExceeded, match="wall time"):
        GraphLangRuntime(g, llm=Slow(), verbose=False, wall_time_s=0.2).execute({})


def test_graf_run_uses_the_bindings_and_a_flag_beats_them(tmp_path):
    g = graph("m")
    g["workflow"]["inputs"] = [{"name": "topic", "type": "TEXT"}]
    g["nodes"][0]["ports"] = ["entry", "out_topic"]
    g["nodes"][1]["config"]["prompt_inline"] = "about {{in_topic}}"
    g["nodes"][1]["ports"].append("in_topic")
    g["edges"].append({"source": "s.out_topic", "target": "g.in_topic", "type": "binds"})
    gp = write(tmp_path / "t.graph.yaml", g)
    bp = write(tmp_path / "t.bind.yaml", {"llm": "mock", "params": {"topic": "tides"}})
    out = CliRunner().invoke(main, ["run", str(gp), "--bind", str(bp), "--no-output", "--no-log"])
    assert out.exit_code == 0 and "tides" in out.output and "adapter: mock" in out.output
    out = CliRunner().invoke(main, ["run", str(gp), "--bind", str(bp), "--param", "topic=waves", "--no-output", "--no-log"])
    assert "waves" in out.output and "tides" not in out.output
    out = CliRunner().invoke(main, ["run", str(gp), "--bind", str(write(tmp_path / "bad.yaml", {"oops": 1}))])
    assert out.exit_code != 0 and "unknown key" in out.output
