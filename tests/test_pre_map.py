"""phases.pre.map: a node computes its inputs from its inputs; an edge `map:` is the same thing written on the arrow."""
import pytest

from graphlang.grafr.edgemap import inject_edge_maps
from graphlang.grafr.lifecycle import check_phases as validate_phases
from graphlang.grafr.nodes import _EXECUTORS, register_executor
from graphlang.grafr.nodes.base import NodeExecutor
from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.topology import check


class Seen(NodeExecutor):
    seen: list = []

    def execute(self, node_data, in_data, context, resolver, llm):
        Seen.seen.append(dict(in_data))
        return {}


@pytest.fixture(autouse=True)
def _seen():
    saved = dict(_EXECUTORS)
    Seen.seen = []
    register_executor("OBSERVE", Seen())
    yield
    _EXECUTORS.clear()
    _EXECUTORS.update(saved)


def graph(pre=None, edge_map=None, extra_edges=()):
    """INPUT.out_text -> b.in_query, with an optional pre.map on b or a map on that edge."""
    b = {"id": "b", "type": "OBSERVE", "ports": ["trigger", "complete", "in_query", "in_n"]}
    if pre:
        b["config"] = {"phases": {"pre": pre}}
    edge = {"source": "s.out_text", "target": "b.in_query", "type": "binds"}
    if edge_map:
        edge["map"] = edge_map
    return {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [{"name": "text", "type": "TEXT"}], "outputs": []},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_text"]}, b],
            "edges": [{"source": "s.entry", "target": "b.trigger", "type": "triggers"}, edge, *extra_edges]}


def run(g, text="  hello  "):
    inject_edge_maps(g)
    GraphLangRuntime(g, verbose=False).execute({"text": text})
    return Seen.seen[-1]


def test_pre_map_replaces_an_input_with_its_expression():
    assert run(graph(pre={"map": {"in_query": "upper(strip(@in_query))"}}))["in_query"] == "HELLO"


def test_a_map_sees_the_inputs_as_they_were_before_any_map_ran():
    g = graph(pre={"defaults": {"in_n": "x"}, "map": {"in_query": "strip(@in_query) + @in_n", "in_n": "upper(@in_n)"}})
    seen = run(g)
    assert seen["in_query"] == "hellox" and seen["in_n"] == "X"           # in_query read the old in_n, not the mapped one


def test_an_edge_map_is_injected_into_the_target_nodes_pre_map():
    g = graph(edge_map="strip(@in_query)")
    inject_edge_maps(g)
    assert g["nodes"][1]["config"]["phases"]["pre"]["map"] == {"in_query": "strip(@in_query)"} and "map" not in g["edges"][1]
    assert run(graph(edge_map="strip(@in_query)"))["in_query"] == "hello"


def test_an_edge_map_works_through_check_and_a_second_load():
    g = graph(edge_map="strip(@in_query)")
    assert check(g)[0] == []
    inject_edge_maps(g)                                                      # idempotent: the map is already in the node
    assert g["nodes"][1]["config"]["phases"]["pre"]["map"] == {"in_query": "strip(@in_query)"}


def test_a_map_on_a_port_with_two_writers_is_refused():
    second = {"source": "s.out_text", "target": "b.in_query", "type": "binds"}
    with pytest.raises(ValueError, match="several writers"):
        inject_edge_maps(graph(edge_map="strip(@in_query)", extra_edges=[second]))


def test_a_map_on_a_triggers_edge_or_a_bad_target_is_refused():
    g = graph()
    g["edges"][0]["map"] = "strip(@in_query)"
    with pytest.raises(ValueError, match="only a binds edge"):
        inject_edge_maps(g)
    g = graph(edge_map="strip(@in_query)")
    g["edges"][1]["target"] = "b.trigger"
    with pytest.raises(ValueError, match="in_\\* port"):
        inject_edge_maps(g)


def test_a_port_mapped_twice_is_refused():
    with pytest.raises(ValueError, match="already maps"):
        inject_edge_maps(graph(pre={"map": {"in_query": "@in_query"}}, edge_map="strip(@in_query)"))


def test_validate_checks_the_map():
    node = {"id": "b", "ports": ["trigger", "complete", "in_query"], "config": {"phases": {"pre": {"map": {"in_nope": "@in_query", "in_query": "@in_other"}}}}}
    errors = validate_phases(node)
    assert any("in_nope" in e and "not an in_* port" in e for e in errors)
    assert any("@in_other" in e for e in errors)
    node["config"]["phases"]["pre"]["map"] = {"in_query": "strip(@in_query"}
    assert any("phases.pre.map.in_query" in e for e in validate_phases(node))


def test_a_map_that_fails_names_the_node_and_the_port():
    with pytest.raises(ValueError, match="node 'b': phases.pre.map.in_query"):
        run(graph(pre={"map": {"in_query": "int(@in_query)"}}), text="not a number")


def test_a_map_on_a_loop_is_refused_because_a_loop_does_not_run_phases():
    node = {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit", "in_x"], "config": {"phases": {"pre": {"map": {"in_x": "@in_x"}}}}}
    assert any("not applied to a LOOP" in e for e in validate_phases(node))
