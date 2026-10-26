"""Static checks on the shipped graphs (wiring, resources, conditions) and on the checker itself."""
from pathlib import Path

import pytest

from graphlang.grafr.runtime import load_graph
from graphlang.grafr.topology import check

COOKBOOK = Path(__file__).parent.parent / "cookbook"
GRAPHS = sorted(COOKBOOK.rglob("*.graph.yaml"))


def test_there_are_graphs_to_check():
    assert len(GRAPHS) >= 3


@pytest.mark.parametrize("path", GRAPHS, ids=lambda p: p.parent.name)
def test_shipped_graphs_have_no_wiring_errors(path):
    errors, warnings = check(load_graph(path))
    warnings = [w for w in warnings if "graflang[kernel]" not in w]       # the optional extra may not be installed here
    assert errors == [], errors
    assert warnings == [], warnings


def graph(nodes, edges, resources=None, inputs=()):
    return {"version": "1.0-graph", "_source_dir": str(COOKBOOK), "resources": resources or {},
            "workflow": {"name": "t", "inputs": list(inputs), "outputs": []}, "nodes": nodes, "edges": edges}


ENTRY = {"id": "s", "type": "INPUT", "ports": ["entry"]}


def errs(nodes, edges, **kw):
    return check(graph([ENTRY, *nodes], edges, **kw))[0]


def test_the_checker_reports_each_kind_of_mistake():
    n = lambda i, t="SOLVE", ports=("trigger", "complete", "in_x", "out_y"), **cfg: {"id": i, "type": t, "ports": list(ports), "config": cfg}
    e = lambda a, b, t="triggers": {"source": a, "target": b, "type": t}
    assert any("no node 'ghost'" in m for m in errs([n("a")], [e("s.entry", "ghost.trigger")]))
    assert any("has no port 'nope'" in m for m in errs([n("a")], [e("s.entry", "a.nope")]))
    assert any("must leave a control port" in m for m in errs([n("a")], [e("a.out_y", "a.trigger")]))
    assert any("must end at a trigger port" in m for m in errs([n("a")], [e("s.entry", "a.in_x")]))
    assert any("binds edge goes from an out_" in m for m in errs([n("a"), n("b")], [e("a.complete", "b.in_x", "binds")]))
    assert any("duplicate node id" in m for m in errs([n("a"), n("a")], []))
    assert any("no condition" in m for m in errs([n("g", "EVALUATE", ("trigger", "pass", "fail"))], []))
    assert any("@zzz" in m for m in errs([n("g", "ASSERT", ("trigger", "pass", "fail", "in_v"), condition="@in_v > @zzz")], []))
    assert any("only these functions" in m for m in errs(
        [n("g", "ASSERT", ("trigger", "pass", "fail"), condition="__import__('os')")], []))
    assert any("no policy_ref" in m for m in errs([n("g", "GUARD", ("trigger", "allow", "deny"))], []))
    assert any("missing port 'deny'" in m for m in errs([n("g", "GUARD", ("trigger", "allow"), policy_ref="policies.p")], []))
    assert any("no policy_ref" in m for m in errs([n("m", "MUTATE", ("trigger", "applied", "rejected", "in_delta"))], []))
    assert any("needs prompt_ref" in m for m in errs([n("g", "GENERATE")], []))
    assert any("does not exist" in m for m in errs(
        [n("g", "GENERATE", prompt_ref="prompts.p")], [], resources={"prompts": {"p": "./nope.md"}}))
    assert any("expected exactly one INPUT" in m for m in check(graph([], []))[0])


def test_loop_checks_cover_the_body_and_the_outputs():
    body = {"nodes": [{"id": "w", "type": "SOLVE", "config": {"expression": "1"}, "ports": ["trigger", "complete", "out_v"]}], "edges": []}
    loop = lambda **cfg: {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit", "in_n", "out_total"],
                          "config": {"subgraph": body, **cfg}}
    assert any("needs a condition" in m for m in errs([loop()], []))
    assert any("@nope" in m for m in errs([loop(condition="@nope")], []))
    assert not [m for m in errs([loop(condition="@in_n > @cycle")], []) if "condition" in m]
    assert any("subgraph has no node 'x'" in m for m in errs([loop(max_iterations=1, outputs={"total": {"from": "x.out_v"}})], []))
    assert any("has no port 'out_zz'" in m for m in errs([loop(max_iterations=1, outputs={"total": {"from": "w.out_zz"}})], []))
    assert any("exactly one of" in m for m in errs([loop(max_iterations=1, outputs={"total": {}})], []))
    assert not errs([loop(max_iterations=1, outputs={"total": {"from": "w.out_v"}})], [])
    loopless = {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"max_iterations": 1}}
    assert any("no subgraph" in m for m in errs([loopless], []))


def test_runtime_rejects_edges_to_missing_ports():
    from graphlang.grafr.runtime import GraphLangRuntime
    g = graph([ENTRY, {"id": "a", "type": "SOLVE", "ports": ["trigger"]}], [{"source": "s.entry", "target": "a.nope", "type": "triggers"}])
    with pytest.raises(ValueError, match="no port 'nope'"):
        GraphLangRuntime(g, verbose=False)


# ---- every risky node is behind a GUARD ---------------------------------------------------------------------------------

def guarded(*, risky_after_guard=True, via_deny=False, extra_path=False, marked=True, typ="OUTPUT", loop=False):
    n = lambda i, t="SOLVE", ports=("trigger", "complete"), **cfg: {"id": i, "type": t, "ports": list(ports), "config": cfg}
    e = lambda a, b: {"source": a, "target": b, "type": "triggers"}
    risky = n("r", typ, ("trigger", "exit", "complete"), **({"risky": True} if marked else {}))
    nodes = [n("work"), n("g", "GUARD", ("trigger", "allow", "deny", "in_v"), policy_ref="policies.p", context_mapping={}), risky]
    edges = [e("s.entry", "work.trigger"), e("work.complete", "g.trigger"),
             e("g.deny" if via_deny else "g.allow", "r.trigger")]
    if extra_path:
        edges.append(e("work.complete", "r.trigger"))
    if loop:
        body = {"nodes": [{"id": "inner", "type": "EMIT", "ports": ["trigger", "complete"]}], "edges": []}
        nodes[2] = {"id": "r", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"subgraph": body, "max_iterations": 1}}
    return [m for m in errs(nodes, edges, resources={"policies": {"p": "./x.cedar"}}) if "risky" in m or "denies" in m]


def test_a_risky_node_behind_a_guard_allow_is_fine():
    assert guarded() == [] and guarded(typ="EMIT", marked=False) == []


def test_a_risky_node_with_a_path_around_the_guard_is_an_error():
    msgs = guarded(extra_path=True)
    assert len(msgs) == 1 and "without passing a GUARD" in msgs[0] and "'r'" in msgs[0]


def test_a_risky_node_on_the_deny_branch_is_an_error():
    assert any("after GUARD 'g' denies" in m for m in guarded(via_deny=True))


def test_emit_and_query_are_risky_by_type_and_other_nodes_only_when_marked():
    assert any("EMIT 'r'" in m for m in guarded(typ="EMIT", marked=False, extra_path=True))
    assert guarded(typ="OUTPUT", marked=False, extra_path=True) == []


def test_a_loop_whose_body_holds_a_risky_node_must_be_guarded_as_a_whole():
    assert guarded(loop=True) == []
    msgs = guarded(loop=True, extra_path=True)
    assert len(msgs) == 1 and "LOOP 'r'" in msgs[0] and "body holds risky r/inner" in msgs[0]
