"""LOOP subgraph execution, condition-driven EVALUATE/ASSERT, and the LLM plumbing, with no real LLM."""
from pathlib import Path

import pytest

from graphlang.grafr.nodes import _EXECUTORS, register_executor
from graphlang.grafr.nodes.base import NodeExecutor
from graphlang.grafr.runtime import GraphLangRuntime, RunLimitExceeded, load_graph

COOKBOOK = Path(__file__).parent.parent / "cookbook"


class FakeLLM:
    """Records prompts; answers from a script (cycled), else echoes."""
    name = "fake"
    model_override = None

    def __init__(self, answers=None):
        self.answers, self.prompts, self.models = list(answers or []), [], []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        self.models.append(model)
        return self.answers[(len(self.prompts) - 1) % len(self.answers)] if self.answers else f"echo:{prompt[:20]}"


class Func(NodeExecutor):
    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def execute(self, node_data, in_data, context, resolver, llm):
        self.calls += 1
        return self.fn(in_data, self.calls)


@pytest.fixture(autouse=True)
def _restore_executors():
    saved = dict(_EXECUTORS)
    yield
    _EXECUTORS.clear()
    _EXECUTORS.update(saved)


def graph(nodes, edges, inputs=(), outputs=()):
    return {"version": "1.0-graph", "workflow": {"name": "t", "inputs": list(inputs), "outputs": list(outputs)},
            "nodes": nodes, "edges": edges}


def trig(a, b):
    return {"source": a, "target": b, "type": "triggers"}


def bind(a, b):
    return {"source": a, "target": b, "type": "binds"}


ENTRY = {"id": "start", "type": "INPUT", "ports": ["entry", "out_n"]}
EXIT = {"id": "end", "type": "OUTPUT", "ports": ["trigger", "exit", "in_result"]}


def loop_graph(loop_cfg, body_nodes, body_edges, loop_ports=("in_n", "out_total")):
    loop = {"id": "lp", "type": "LOOP", "ports": ["trigger", "loop", "exit", *loop_ports], "config":
            {**loop_cfg, "subgraph": {"nodes": body_nodes, "edges": body_edges}}}
    return graph([ENTRY, loop, EXIT],
                 [trig("start.entry", "lp.trigger"), trig("lp.exit", "end.trigger"),
                  bind("start.out_n", "lp.in_n"), bind("lp.out_total", "end.in_result")],
                 inputs=[{"name": "n", "type": "INTEGER"}], outputs=[{"name": "total", "type": "TEXT"}])


def test_loop_runs_the_body_until_the_condition_stops_it():
    register_executor("SOLVE", Func(lambda d, n: {"out_v": d["in_i"] * 10}))
    g = loop_graph({"condition": "@i < @in_n", "index_var": "i", "outputs": {"total": {"collect": "step.out_v"}}},
                   [{"id": "step", "type": "SOLVE", "ports": ["trigger", "complete", "in_i", "out_v"]}], [])
    rt = GraphLangRuntime(g, verbose=False)
    assert rt.execute({"n": 4}) == {"total": [0, 10, 20, 30]}          # in_i read the loop counter by name
    assert rt.loop_iterations == {"lp": 4}


def test_loop_with_false_condition_never_runs_the_body_and_max_iterations_caps_it():
    ex = Func(lambda d, n: {"out_v": n})
    register_executor("SOLVE", ex)
    body = [{"id": "step", "type": "SOLVE", "ports": ["trigger", "complete", "out_v"]}]
    out = {"total": {"from": "step.out_v"}}
    assert GraphLangRuntime(loop_graph({"condition": "@in_n > 100", "outputs": out}, body, []), verbose=False).execute({"n": 1}) == {"total": None}
    assert ex.calls == 0
    ex.calls = 0
    GraphLangRuntime(loop_graph({"condition": "true", "max_iterations": "@in_n", "outputs": out}, body, []), verbose=False).execute({"n": 5})
    assert ex.calls == 5
    ex.calls = 0
    GraphLangRuntime(loop_graph({"max_iterations": 2, "outputs": out}, body, []), verbose=False).execute({"n": 5})
    assert ex.calls == 2


def test_loop_fired_output_and_data_binds_inside_the_body():
    register_executor("SOLVE", Func(lambda d, n: {"out_v": n}))
    body = [{"id": "step", "type": "SOLVE", "ports": ["trigger", "complete", "out_v"]},
            {"id": "gate", "type": "EVALUATE", "ports": ["trigger", "pass", "fail", "in_v"],
             "config": {"condition": "@in_v >= 3"}}]
    edges = [trig("step.complete", "gate.trigger"), bind("step.out_v", "gate.in_v")]
    cfg = {"condition": "NOT @ok AND @cycle < 10",
           "outputs": {"ok": {"fired": "gate.pass"}, "total": {"from": "step.out_v"}}}
    rt = GraphLangRuntime(loop_graph(cfg, body, edges, loop_ports=("in_n", "out_total", "out_ok")), verbose=False)
    assert rt.execute({"n": 0}) == {"total": 3}                          # stopped when the gate first passed
    assert rt.loop_iterations == {"lp": 3}


def test_loop_validation_errors():
    body = [{"id": "step", "type": "SOLVE", "ports": ["trigger", "complete"]}]
    with pytest.raises(ValueError, match="needs a condition or max_iterations"):
        GraphLangRuntime(loop_graph({}, body, []), verbose=False).execute({"n": 1})
    with pytest.raises(ValueError, match="exactly one of from/collect/fired"):
        GraphLangRuntime(loop_graph({"max_iterations": 1, "outputs": {"x": {"from": "a.b", "collect": "a.b"}}}, body, []),
                         verbose=False).execute({"n": 1})
    with pytest.raises(ValueError, match="LOOP 'lp'.*unknown variable @zzz"):
        GraphLangRuntime(loop_graph({"condition": "@zzz"}, body, []), verbose=False).execute({"n": 1})
    g = loop_graph({"max_iterations": 1}, body, [])
    del g["nodes"][1]["config"]["subgraph"]
    with pytest.raises(ValueError, match="has no subgraph"):
        GraphLangRuntime(g, verbose=False).execute({"n": 1})


def test_a_body_that_retries_forever_hits_the_shared_step_budget():
    register_executor("EVALUATE", Func(lambda d, n: {"_route": "fail"}))
    body = [{"id": "a", "type": "SOLVE", "config": {"expression": "1"}, "ports": ["trigger", "complete"]},
            {"id": "g", "type": "EVALUATE", "ports": ["trigger", "pass", "fail"]}]
    edges = [trig("a.complete", "g.trigger"), trig("g.fail", "a.trigger")]
    # `a` is triggered by g, so nothing starts the body: no start nodes -> nothing runs, loop ends by max_iterations
    rt = GraphLangRuntime(loop_graph({"max_iterations": 2}, body, edges), verbose=False)
    rt.execute({"n": 1})                                                # no start node: nothing runs, no hang
    assert set(rt.fired) == {"lp", "end"}                               # the LOOP and the OUTPUT fired; no body node
    body2 = body + [{"id": "s", "type": "SOLVE", "config": {"expression": "1"}, "ports": ["trigger", "complete"]}]
    edges2 = edges + [trig("s.complete", "a.trigger")]
    with pytest.raises(RunLimitExceeded):
        GraphLangRuntime(loop_graph({"max_iterations": 2}, body2, edges2), verbose=False, max_steps=50).execute({"n": 1})


def test_evaluate_and_assert_use_the_safe_evaluator_and_report_bad_conditions():
    g = graph([ENTRY, {"id": "a", "type": "ASSERT", "ports": ["trigger", "pass", "fail", "in_n"],
                       "config": {"condition": "@in_n % 2 == 0"}},
               {"id": "ok", "type": "OBSERVE", "ports": ["trigger", "complete"]},
               {"id": "bad", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
              [trig("start.entry", "a.trigger"), trig("a.pass", "ok.trigger"), trig("a.fail", "bad.trigger"),
               bind("start.out_n", "a.in_n")], inputs=[{"name": "n", "type": "INTEGER"}])
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"n": "4"})                                              # text from the command line is coerced
    assert "ok" in rt.fired and "bad" not in rt.fired
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"n": 3})
    assert "bad" in rt.fired and "ok" not in rt.fired
    g["nodes"][1]["config"]["condition"] = "__import__('os')"
    with pytest.raises(ValueError, match="ASSERT node 'a'"):
        GraphLangRuntime(g, verbose=False).execute({"n": 1})
    del g["nodes"][1]["config"]["condition"]
    with pytest.raises(ValueError, match="no config.condition"):
        GraphLangRuntime(g, verbose=False).execute({"n": 1})


def test_input_coercion_by_declared_type():
    g = graph([{"id": "start", "type": "INPUT", "ports": ["entry", "out_i", "out_f", "out_b", "out_t"]}, EXIT],
              [trig("start.entry", "end.trigger")],
              inputs=[{"name": "i", "type": "INTEGER"}, {"name": "f", "type": "FLOAT"},
                      {"name": "b", "type": "BOOL"}, {"name": "t", "type": "TEXT"}])
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"i": "3", "f": "0.5", "b": "yes", "t": "3"})
    assert rt.values[("start", "out_i")] == 3 and rt.values[("start", "out_f")] == 0.5
    assert rt.values[("start", "out_b")] is True and rt.values[("start", "out_t")] == "3"
    for bad in ({"i": "x"}, {"b": "maybe"}):
        with pytest.raises(ValueError, match="must be"):
            GraphLangRuntime(g, verbose=False).execute({"i": "1", "f": "1", "b": "true", "t": "t", **bad})


def test_generate_uses_the_run_llm_and_the_model_rules():
    g = graph([ENTRY, {"id": "gen", "type": "GENERATE", "ports": ["trigger", "complete", "in_n", "out_text"],
                       "config": {"prompt_inline": "n is {{in_n}}", "model": "ollama/gemma3"}}, EXIT],
              [trig("start.entry", "gen.trigger"), trig("gen.complete", "end.trigger"),
               bind("start.out_n", "gen.in_n"), bind("gen.out_text", "end.in_result")],
              inputs=[{"name": "n", "type": "INTEGER"}], outputs=[{"name": "t", "type": "TEXT"}])
    llm = FakeLLM(["answer"])
    out = GraphLangRuntime(g, llm=llm, verbose=False).execute({"n": 7})
    assert out == {"t": "answer"} and llm.prompts == ["n is 7"]
    assert llm.models == [None]                                          # an 'ollama/' hint is ignored under 'fake'
    llm2 = FakeLLM(["a"])
    llm2.model_override = "claude-haiku-5-5"
    GraphLangRuntime(g, llm=llm2, verbose=False).execute({"n": 1})
    assert llm2.models == ["claude-haiku-5-5"]                           # the run-time --model wins


def test_procedure_nodes_refuse_a_non_spl_llm_but_run_under_mock(tmp_path):
    (tmp_path / "thing.spl").write_text("-- placeholder\n")
    g = graph([ENTRY, {"id": "p", "type": "GENERATE", "ports": ["trigger", "complete", "out_x"],
                       "config": {"procedure_ref": "procedures.thing"}}],
              [trig("start.entry", "p.trigger")], inputs=[{"name": "n", "type": "INTEGER"}])
    g["_source_dir"] = str(tmp_path)
    g["resources"] = {"procedures": {"thing": "./thing.spl"}}
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"n": 1})                                                  # mock: not run, returns a marker
    assert rt.values[("p", "out_x")].startswith("[Mock procedure procedures.thing]")
    with pytest.raises(NotImplementedError, match="needs an SPL.py adapter"):
        GraphLangRuntime(g, llm=FakeLLM(), verbose=False).execute({"n": 1})


def test_shipped_loops_run_with_a_scripted_llm():
    data = load_graph(COOKBOOK / "concept_book" / "build_concept_book.graph.yaml")
    llm = FakeLLM(["OUTLINE", "CH-A", "REV-A", "CH-B", "REV-B", "BOOK"])
    rt = GraphLangRuntime(data, llm=llm, verbose=False)
    out = rt.execute({"subject": "physics", "num_chapters": "2"})
    assert out == {"book": "BOOK"} and rt.loop_iterations == {"chapter_loop": 2}
    assert "Chapter" in llm.prompts[1] or "chapter" in llm.prompts[1].lower()
    assert "CH-A" in llm.prompts[2]                                      # the review saw the chapter it reviewed
    assert "CH-A" in llm.prompts[-1] and "CH-B" in llm.prompts[-1]       # compile got both chapters (list repr)


def test_flagship_loop_stops_when_tests_pass(tmp_path):
    data = load_graph(COOKBOOK / "code_pipeline" / "code_pipeline.graph.yaml")
    def use_prompts(nodes):                                              # procedures need SPL.py; use prompts
        for n in nodes:
            cfg = n.get("config", {})
            if cfg.get("procedure_ref"):
                n["config"] = {"prompt_inline": "do {{in_spec}}"}
            if "subgraph" in cfg:
                use_prompts(cfg["subgraph"]["nodes"])

    use_prompts(data["nodes"])
    calls = []

    class Tests(NodeExecutor):
        def execute(self, node_data, in_data, context, resolver, llm):
            calls.append(node_data["id"])
            return {"out_result": "[PASSED]" if len(calls) >= 2 else "[FAILED]"}

    register_executor("SOLVE", Tests())
    llm = FakeLLM(["[READY]"])                                           # every generate returns [READY]
    rt = GraphLangRuntime(data, llm=llm, verbose=False)
    out = rt.execute({"spec": "s", "max_cycles": 5, "check_closure": False})
    assert rt.loop_iterations == {"test_gated_loop": 2}                  # failed once, then passed
    assert "docs" in out
