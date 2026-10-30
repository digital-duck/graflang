"""Typed ports (design E2): the mapping form of `ports`, the edge type check, and value checks at run time."""
import pytest

from graphlang.grafr.ports import assignable
from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.topology import check

from test_lifecycle import Scripted


def graph(gen_ports, out_type="TEXT", phases=None):
    gen = {"id": "g", "type": "GENERATE", "ports": gen_ports,
           "config": {"prompt_inline": "hi", **({"phases": phases} if phases else {})}}
    out = {"id": "o", "type": "OUTPUT", "ports": {"trigger": "control", "in_text": out_type}}
    return {"version": "1.0-graph", "resources": {}, "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "text"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry"]}, gen, out],
            "edges": [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
                      {"source": "g.out_text", "target": "o.in_text", "type": "binds"},
                      {"source": "g.complete", "target": "o.trigger", "type": "triggers"}]}


TEXT_GEN = {"trigger": "control", "complete": "control", "out_text": "TEXT"}


def test_mapping_form_runs_and_list_form_still_works():
    rt = GraphLangRuntime(graph(TEXT_GEN), llm=Scripted("hello"), verbose=False)
    assert rt.execute({})["text"] == "hello"
    assert rt.G.nodes["g"]["ports"] == ["trigger", "complete", "out_text"]


def test_assignability():
    assert assignable("INTEGER", "FLOAT") and assignable("LIST", "JSON") and assignable("ANY", "TEXT")
    assert not assignable("TEXT", "INTEGER") and not assignable("TEXT", "JSON") and not assignable("FLOAT", "INTEGER")


def test_validate_rejects_a_binds_edge_between_incompatible_types():
    errs = check(graph(TEXT_GEN, out_type="INTEGER"))[0]
    assert any("TEXT cannot be bound to a INTEGER port" in m for m in errs), errs
    assert check(graph(TEXT_GEN, out_type="ANY"))[0] == []


def test_validate_rejects_unknown_types_and_control_data_mixups():
    errs = check(graph({"trigger": "control", "complete": "control", "out_text": "STRING", "in_x": "control"}))[0]
    assert any("unknown type 'STRING'" in m for m in errs) and any("control type on a data port" in m for m in errs)


def test_a_value_of_the_wrong_type_stops_the_run():
    g = graph({"trigger": "control", "complete": "control", "out_text": "INTEGER"}, out_type="INTEGER")
    with pytest.raises(ValueError, match="is INTEGER but got str"):
        GraphLangRuntime(g, llm=Scripted("not a number"), verbose=False).execute({})


def test_json_port_with_a_schema_checks_the_value():
    schema = {"type": "object", "required": ["n"]}
    ports = {"trigger": "control", "complete": "control", "out_text": {"type": "JSON", "schema": schema}}
    ok = GraphLangRuntime(graph(ports, "JSON", {"post": {"out_schema": schema}}), llm=Scripted('{"n": 1}'), verbose=False)
    assert ok.execute({})["text"] == {"n": 1}
    bad = GraphLangRuntime(graph(ports, "JSON"), llm=Scripted("plain text"), verbose=False)
    with pytest.raises(ValueError):
        bad.execute({})


def test_trust_labels_need_the_sink_labels_on_the_source():
    assert assignable("TEXT!sql_safe", "TEXT!sql_safe") and assignable("TEXT!sql_safe!x", "TEXT!sql_safe")
    assert assignable("TEXT!sql_safe", "TEXT") and assignable("TEXT", "TEXT")
    assert not assignable("TEXT", "TEXT!sql_safe") and not assignable("TEXT!untrusted", "TEXT!sql_safe")
    errs = check(graph({"trigger": "control", "complete": "control", "out_text": "TEXT!untrusted"}, out_type="TEXT!sql_safe"))[0]
    assert any("cannot be bound" in m for m in errs)
    assert check(graph({"trigger": "control", "complete": "control", "out_text": "TEXT!sql_safe"}, out_type="TEXT!sql_safe"))[0] == []
    # the label does not change the runtime value check
    rt = GraphLangRuntime(graph({"trigger": "control", "complete": "control", "out_text": "TEXT!sql_safe"}, "TEXT!sql_safe"),
                          llm=Scripted("select 1"), verbose=False)
    assert rt.execute({})["text"] == "select 1"


def test_workflow_input_types_type_the_input_ports():
    g = graph(TEXT_GEN)
    g["workflow"]["inputs"] = [{"name": "n", "type": "INTEGER"}]
    g["nodes"][0]["ports"] = ["entry", "out_n"]
    g["nodes"][2]["ports"] = {"trigger": "control", "in_text": "TEXT", "in_n": "TEXT"}
    g["edges"].append({"source": "s.out_n", "target": "o.in_n", "type": "binds"})
    assert any("INTEGER cannot be bound to a TEXT port" in m for m in check(g)[0])
