"""grafr runtime: control tokens, port-keyed data, routing, loops, JOIN barriers, schema and resources."""
from pathlib import Path

import pytest

from graphlang.grafr.nodes import _EXECUTORS, register_executor
from graphlang.grafr.nodes.base import NodeExecutor
from graphlang.grafr.runtime import GraphLangRuntime, RunLimitExceeded, load_graph

ROOT = Path(__file__).parent.parent
COOKBOOK = ROOT / "cookbook"


@pytest.fixture(autouse=True)
def _restore_executors():
    saved = dict(_EXECUTORS)
    yield
    _EXECUTORS.clear()
    _EXECUTORS.update(saved)


def graph(nodes, edges, inputs=(), outputs=()):
    return {"version": "1.0-graph",
            "workflow": {"name": "t", "inputs": list(inputs), "outputs": list(outputs)},
            "nodes": nodes, "edges": edges}


def trig(a, b):
    return {"source": a, "target": b, "type": "triggers"}


def bind(a, b):
    return {"source": a, "target": b, "type": "binds"}


class Func(NodeExecutor):
    """Test executor: calls fn(in_data, state) and returns its dict."""
    def __init__(self, fn):
        self.fn, self.state = fn, {"calls": 0}

    def execute(self, node_data, in_data, context, resolver, adapter):
        self.state["calls"] += 1
        return self.fn(in_data, self.state)


ENTRY = {"id": "start", "type": "INPUT", "ports": ["entry", "out_x"]}
EXIT = {"id": "end", "type": "OUTPUT", "ports": ["trigger", "exit", "in_result"]}


def test_data_flows_by_port_and_outputs_use_declared_names():
    register_executor("SOLVE", Func(lambda d, s: {"out_y": d["in_x"] + 1}))
    g = graph([ENTRY, {"id": "inc", "type": "SOLVE", "ports": ["trigger", "complete", "in_x", "out_y"]}, EXIT],
              [trig("start.entry", "inc.trigger"), trig("inc.complete", "end.trigger"),
               bind("start.out_x", "inc.in_x"), bind("inc.out_y", "end.in_result")],
              inputs=[{"name": "x", "type": "INTEGER"}], outputs=[{"name": "answer", "type": "INTEGER"}])
    assert GraphLangRuntime(g, verbose=False).execute({"x": 41}) == {"answer": 42}


def test_defaults_and_input_checks():
    g = graph([ENTRY, EXIT], [trig("start.entry", "end.trigger"), bind("start.out_x", "end.in_result")],
              inputs=[{"name": "x", "type": "TEXT", "default": "d"}], outputs=[{"name": "r", "type": "TEXT"}])
    assert GraphLangRuntime(g, verbose=False).execute() == {"r": "d"}
    with pytest.raises(ValueError, match="unknown workflow input"):
        GraphLangRuntime(g, verbose=False).execute({"nope": 1})
    g["workflow"]["inputs"][0].pop("default")
    with pytest.raises(ValueError, match="missing workflow input"):
        GraphLangRuntime(g, verbose=False).execute()


def test_trigger_and_bind_edges_between_the_same_nodes_both_survive():
    """Regression: a plain DiGraph kept one edge per node pair, so the later edge overwrote the earlier."""
    register_executor("SOLVE", Func(lambda d, s: {"out_y": d.get("in_x")}))
    g = graph([ENTRY, {"id": "a", "type": "SOLVE", "ports": ["trigger", "complete", "in_x", "out_y"]}],
              [trig("start.entry", "a.trigger"), bind("start.out_x", "a.in_x")],
              inputs=[{"name": "x", "type": "TEXT"}])
    rt = GraphLangRuntime(g, verbose=False)
    assert rt.G.number_of_edges() == 2
    rt.execute({"x": "v"})
    assert rt.values[("a", "out_y")] == "v"
    g2 = graph([ENTRY, {"id": "a", "type": "SOLVE", "ports": ["trigger", "complete", "in_x", "in_z", "out_y"]}],
               [trig("start.entry", "a.trigger"), bind("start.out_x", "a.in_x"), bind("start.out_x", "a.in_z")],
               inputs=[{"name": "x", "type": "TEXT"}])
    assert GraphLangRuntime(g2, verbose=False).G.number_of_edges() == 3        # parallel edges on different ports


def test_routing_follows_the_chosen_port_only():
    register_executor("EVALUATE", Func(lambda d, s: {"_route": "fail"}))
    marks = []
    register_executor("SOLVE", Func(lambda d, s: marks.append("ran") or {}))
    g = graph([ENTRY, {"id": "gate", "type": "EVALUATE", "ports": ["trigger", "pass", "fail"]},
               {"id": "yes", "type": "SOLVE", "ports": ["trigger", "complete"]},
               {"id": "no", "type": "GENERATE", "ports": ["trigger", "complete", "out_t"],
                "config": {"prompt_inline": "p"}}],
              [trig("start.entry", "gate.trigger"), trig("gate.pass", "yes.trigger"), trig("gate.fail", "no.trigger")])
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({})
    assert marks == [] and rt.fired == {"gate": 1, "no": 1}
    register_executor("EVALUATE", Func(lambda d, s: {"_route": "nowhere"}))
    with pytest.raises(ValueError, match="not one of its ports"):
        GraphLangRuntime(g, verbose=False).execute({})


def test_retry_wire_loops_until_the_gate_passes():
    """Regression: a visited set meant a node never ran twice, so a retry wire did nothing."""
    register_executor("SOLVE", Func(lambda d, s: {"out_n": s["calls"]}))
    register_executor("EVALUATE", Func(lambda d, s: {"_route": "pass" if d["in_n"] >= 3 else "fail"}))
    g = graph([ENTRY, {"id": "work", "type": "SOLVE", "ports": ["trigger", "complete", "out_n"]},
               {"id": "gate", "type": "EVALUATE", "ports": ["trigger", "pass", "fail", "in_n"]}, EXIT],
              [trig("start.entry", "work.trigger"), trig("work.complete", "gate.trigger"),
               trig("gate.fail", "work.trigger"), trig("gate.pass", "end.trigger"),
               bind("work.out_n", "gate.in_n"), bind("work.out_n", "end.in_result")],
              outputs=[{"name": "n", "type": "INTEGER"}])
    rt = GraphLangRuntime(g, verbose=False)
    assert rt.execute({}) == {"n": 3} and rt.fired["work"] == 3


def test_a_loop_that_never_exits_is_stopped():
    register_executor("EVALUATE", Func(lambda d, s: {"_route": "fail"}))
    g = graph([ENTRY, {"id": "work", "type": "SOLVE", "config": {"expression": "1"}, "ports": ["trigger", "complete"]},
               {"id": "gate", "type": "EVALUATE", "ports": ["trigger", "pass", "fail"]}],
              [trig("start.entry", "work.trigger"), trig("work.complete", "gate.trigger"),
               trig("gate.fail", "work.trigger")])
    with pytest.raises(RunLimitExceeded, match="stopped after 20"):
        GraphLangRuntime(g, verbose=False, max_steps=20).execute({})


def test_fork_fans_out_and_join_waits_for_every_branch():
    seen = []
    register_executor("SOLVE", Func(lambda d, s: seen.append("branch") or {}))
    register_executor("OBSERVE", Func(lambda d, s: seen.append("after-join") or {}))
    g = graph([ENTRY, {"id": "f", "type": "FORK", "ports": ["trigger", "b1", "b2"]},
               {"id": "p", "type": "SOLVE", "ports": ["trigger", "complete"]},
               {"id": "q", "type": "SOLVE", "ports": ["trigger", "complete"]},
               {"id": "j", "type": "JOIN", "ports": ["trigger", "complete"]},
               {"id": "after", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
              [trig("start.entry", "f.trigger"), trig("f.b1", "p.trigger"), trig("f.b2", "q.trigger"),
               trig("p.complete", "j.trigger"), trig("q.complete", "j.trigger"), trig("j.complete", "after.trigger")])
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({})
    assert seen == ["branch", "branch", "after-join"] and rt.fired["j"] == 1


def test_unknown_node_in_an_edge_is_rejected():
    g = graph([ENTRY], [trig("start.entry", "ghost.trigger")])
    with pytest.raises(ValueError, match="unknown node 'ghost'"):
        GraphLangRuntime(g, verbose=False)


def test_schema_accepts_guard_and_the_shipped_examples_load():
    for p in COOKBOOK.rglob("*.graph.yaml"):
        data = load_graph(p)
        assert data["_source_dir"] == str(p.parent.resolve())


def test_schema_errors_say_where(tmp_path):
    bad = tmp_path / "bad.graph.yaml"
    bad.write_text('version: "1.0-graph"\nworkflow: {name: x}\nnodes:\n  - {id: a, type: TELEPORT, ports: [trigger]}\nedges: []\n')
    with pytest.raises(ValueError, match=r"nodes/0/type"):
        load_graph(bad)


def test_self_refine_runs_end_to_end_with_the_mock_llm():
    data = load_graph(COOKBOOK / "self_refine" / "self_refine.graph.yaml")
    rt = GraphLangRuntime(data, verbose=False)
    out = rt.execute({"topic": "gravity"})
    assert rt.fired == {"draft": 1, "critique": 1, "refine": 1, "wf_exit": 1}      # the entry node only emits
    assert "essay" in out and out["essay"].startswith("[Mock LLM response")
    assert "gravity" in rt.values[("draft", "out_essay")]                  # the topic reached the prompt


def test_resolver_honours_the_resources_block(tmp_path):
    from graphlang.grafr.resolver import ResourceResolver
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "p.md").write_text("hi")
    r = ResourceResolver(tmp_path, {"prompts": {"p": "./elsewhere/p.md"}})
    assert r.resolve("prompts.p", "prompts")["content"] == "hi"
    with pytest.raises(FileNotFoundError):
        r.resolve("prompts.q", "prompts")
    with pytest.raises(ValueError, match="Unknown resource type"):
        r.resolve("x", "widgets")


def test_when_several_binds_feed_one_port_the_latest_write_wins():
    register_executor("SOLVE", Func(lambda d, s: {"out_v": "first"}))
    register_executor("OBSERVE", Func(lambda d, s: {"out_v": "second"}))
    g = graph([ENTRY, {"id": "a", "type": "SOLVE", "ports": ["trigger", "complete", "out_v"]},
               {"id": "b", "type": "OBSERVE", "ports": ["trigger", "complete", "out_v"]}, EXIT],
              [trig("start.entry", "a.trigger"), trig("a.complete", "b.trigger"), trig("b.complete", "end.trigger"),
               bind("b.out_v", "end.in_result"), bind("a.out_v", "end.in_result")],      # b is listed first, a last
              outputs=[{"name": "r", "type": "TEXT"}])
    assert GraphLangRuntime(g, verbose=False).execute({}) == {"r": "second"}             # b wrote later
