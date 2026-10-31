"""Node ids that clash with the file's own syntax are refused by `graf validate` (see "Reserved words" in the USER-GUIDE)."""
import copy

import pytest

from graphlang.grafr.compact import CompactError, expand
from graphlang.grafr.runtime import load_graph
from graphlang.grafr.topology import check
from test_parts import GRAPH

BASE = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "text", "type": "TEXT"}]},
        "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry"]},
                  {"id": "g", "type": "GENERATE", "ports": ["trigger", "complete", "out_text"], "config": {"prompt_inline": "hi"}},
                  {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_text"]}],
        "edges": [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
                  {"source": "g.out_text", "target": "o.in_text", "type": "binds"},
                  {"source": "g.complete", "target": "o.trigger", "type": "triggers"}]}


def renamed(new_id):
    g = copy.deepcopy(BASE)
    node = g["nodes"][1]
    for e in g["edges"]:
        for side in ("source", "target"):
            if e[side].startswith("g."):
                e[side] = e[side].replace("g.", new_id + ".", 1)
    node["id"] = new_id
    return g


def test_a_clean_graph_passes():
    assert check(copy.deepcopy(BASE)) == ([], [])


@pytest.mark.parametrize("bad, message", [("a b", "may not contain"), ("a/b", "may not contain"), ("a__b", "'__' in an id is reserved")])
def test_a_clashing_id_is_named(bad, message):
    errors, _ = check(renamed(bad))
    assert any(message in e for e in errors), errors


def test_an_id_inside_a_loop_body_is_checked_too():
    g = copy.deepcopy(BASE)
    body = {"nodes": [{"id": "x__y", "type": "GENERATE", "ports": ["trigger"], "config": {"prompt_inline": "x"}}], "edges": []}
    g["nodes"].append({"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"subgraph": body, "max_iterations": 1}})
    errors, _ = check(g)
    assert any("lp/" in e and "'__'" in e for e in errors), errors


def test_the_ids_a_part_expands_to_are_allowed():
    errors, _ = check(load_graph(GRAPH))
    assert not any("reserved" in e for e in errors)         # first__rewrite and second__rewrite are the loader's


def test_a_compact_step_id_with_double_underscore_is_refused():
    with pytest.raises(CompactError, match="reserved"):
        expand({"version": "1.0-graph", "workflow": {"name": "t", "inputs": [], "outputs": []},
                        "steps": [{"a__b": {"generate": "hi"}}]})
