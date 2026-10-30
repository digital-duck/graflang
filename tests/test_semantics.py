"""Characterization tests for the scheduler: each test pins one rule of docs/DEV/DESIGN/graflang-semantics.md.

They describe what the runtime does today. A rule that looks like an accident is marked `ACCIDENT`: it is pinned so a change is
noticed and decided on purpose, not because it is the intended meaning.
"""
import pytest

from graphlang.grafr.nodes import _EXECUTORS, register_executor
from graphlang.grafr.nodes.base import NodeExecutor
from graphlang.grafr.runtime import GraphLangRuntime, RunLimitExceeded


@pytest.fixture(autouse=True)
def _restore_executors():
    saved = dict(_EXECUTORS)
    yield
    _EXECUTORS.clear()
    _EXECUTORS.update(saved)


class Emit(NodeExecutor):
    """Writes `config.out` to out_y and routes to `config.route` if set; records its inputs."""
    seen: list = []

    def execute(self, node_data, in_data, context, resolver, llm):
        cfg = node_data.get("config", {})
        Emit.seen.append((node_data["id"], dict(in_data)))
        res = {"out_y": cfg.get("out")} if "out" in cfg else {}
        if "route" in cfg:
            res["_route"] = cfg["route"]
        return res


@pytest.fixture(autouse=True)
def _emit():
    Emit.seen = []
    register_executor("OBSERVE", Emit())


def n(i, t="OBSERVE", ports=("trigger", "complete", "in_x", "out_y"), **cfg):
    return {"id": i, "type": t, "ports": list(ports), "config": cfg}


def e(a, b, t="triggers"):
    return {"source": a, "target": b, "type": t}


START = {"id": "s", "type": "INPUT", "ports": ["entry"]}


def run(nodes, edges, **kw):
    g = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [], "outputs": []}, "nodes": [START, *nodes], "edges": edges}
    rt = GraphLangRuntime(g, verbose=False, **kw)
    rt.execute({})
    return rt


def read(node):
    return [d for i, d in Emit.seen if i == node]


# R1: a node fires when a control token reaches it; a node nothing triggers never fires.
def test_only_a_triggered_node_fires():
    rt = run([n("a"), n("lonely")], [e("s.entry", "a.trigger")])
    assert rt.fired == {"a": 1}          # the INPUT node emits at start without firing


# R2: with no `_route`, a node emits on the first of complete / exit / entry; FORK emits on every control port.
def test_default_emission_and_fork():
    rt = run([n("f", "FORK", ("trigger", "a", "b")), n("x"), n("y")], [e("s.entry", "f.trigger"), e("f.a", "x.trigger"), e("f.b", "y.trigger")])
    assert rt.fired["x"] == rt.fired["y"] == 1


# R3: `_route` picks exactly one control port.
def test_a_route_chooses_one_port():
    rt = run([n("g", ports=("trigger", "pass", "fail"), route="fail"), n("p"), n("f")],
             [e("s.entry", "g.trigger"), e("g.pass", "p.trigger"), e("g.fail", "f.trigger")])
    assert "f" in rt.fired and "p" not in rt.fired


# R4: a JOIN fires once, after a token has arrived over every incoming `triggers` edge.
def test_join_waits_for_every_incoming_edge():
    rt = run([n("f", "FORK", ("trigger", "a", "b")), n("x"), n("y"), n("j", "JOIN", ("trigger", "complete"))],
             [e("s.entry", "f.trigger"), e("f.a", "x.trigger"), e("f.b", "y.trigger"), e("x.complete", "j.trigger"), e("y.complete", "j.trigger")])
    assert rt.fired["j"] == 1


# R5: an input holds the value most recently written by any of its `binds` sources, in write order (a run's clock), not edge order.
@pytest.mark.parametrize("order", [0, 1])
def test_latest_write_wins_whatever_the_edge_order(order):
    binds = [e("a.out_y", "c.in_x", "binds"), e("b.out_y", "c.in_x", "binds")]
    rt = run([n("a", out="from A"), n("b", out="from B"), n("c")],
             [e("s.entry", "a.trigger"), e("a.complete", "b.trigger"), e("b.complete", "c.trigger"), *binds[::1 if order else -1]])
    assert read("c") == [{"in_x": "from B"}]


# R6 (ACCIDENT): a value stays on its port after the node that wrote it has finished, so a later reader sees it even though
# nothing wrote it for this activation. Stale reads are possible; there is no per-activation versioning.
def test_a_value_outlives_its_writer():
    rt = run([n("a", out="old"), n("c"), n("c2")],
             [e("s.entry", "a.trigger"), e("a.complete", "c.trigger"), e("c.complete", "c2.trigger"),
              e("a.out_y", "c2.in_x", "binds")])
    assert read("c2") == [{"in_x": "old"}]


# R7: an input nothing has written is simply absent from the node's inputs (no error).
def test_unwritten_inputs_are_absent():
    run([n("a"), n("c")], [e("s.entry", "a.trigger"), e("a.complete", "c.trigger"), e("a.out_y", "c.in_x", "binds")])
    assert read("c") == [{}]


# R8: a node can fire many times (a retry wire is a loop); `max_steps` bounds a run that never ends.
def test_a_cycle_is_stopped_by_the_step_budget():
    with pytest.raises(RunLimitExceeded):
        run([n("a")], [e("s.entry", "a.trigger"), e("a.complete", "a.trigger")], max_steps=20)


# R9: a LOOP checks its condition before each iteration, so a false condition runs the body zero times.
def test_loop_condition_is_checked_before_the_first_iteration():
    body = {"nodes": [{"id": "b", "type": "OBSERVE", "ports": ["trigger", "complete"]}], "edges": []}
    lp = {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"condition": "@cycle < 0", "subgraph": body}}
    rt = run([lp], [e("s.entry", "lp.trigger")])
    assert rt.loop_iterations == {"lp": 0}


# R10: each LOOP iteration runs in a fresh copy of the body: what a body node wrote in one iteration is not visible in the next,
# except through the loop's declared outputs.
def test_loop_iterations_do_not_share_body_values():
    body = {"nodes": [{"id": "r", "type": "OBSERVE", "ports": ["trigger", "complete", "in_x", "out_y"], "config": {"out": "v"}},
                      {"id": "w", "type": "OBSERVE", "ports": ["trigger", "complete", "in_x"]}],
            "edges": [e("w.complete", "r.trigger"), e("r.out_y", "w.in_x", "binds")]}
    lp = {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"max_iterations": 2, "subgraph": body}}
    run([lp], [e("s.entry", "lp.trigger")])
    assert read("w") == [{}, {}]    # `w` starts each iteration, before `r` writes; in iteration 2 it still sees nothing from iteration 1


# ---- JOIN as fan-in (design decision 2) -------------------------------------------------------------------------------

def test_join_bundles_named_inputs_into_one_object_and_a_reader_takes_a_field():
    nodes = [n("s", "INPUT", ("entry",)), n("f", "FORK", ("trigger", "a", "b")),
             n("A", out=3), n("B", out=4),
             n("j", "JOIN", ("trigger", "complete", "in_x", "in_y", "out_args")),
             n("C", "SOLVE", ("trigger", "complete", "in_args", "out_y"), expression="@in_args.x + @in_args.y")]
    edges = [e("s.entry", "f.trigger"), e("f.a", "A.trigger"), e("f.b", "B.trigger"),
             e("A.complete", "j.trigger"), e("B.complete", "j.trigger"),
             e("A.out_y", "j.in_x", "binds"), e("B.out_y", "j.in_y", "binds"),
             e("j.out_args", "C.in_args", "binds"), e("j.complete", "C.trigger")]
    rt = GraphLangRuntime({"version": "1.0-graph", "_source_dir": ".", "resources": {},
                           "workflow": {"name": "t", "inputs": [], "outputs": []}, "nodes": nodes, "edges": edges},
                          verbose=False)
    rt.execute({})
    assert rt.values[("j", "out_args")] == {"x": 3, "y": 4} and rt.values[("C", "out_y")] == 7
