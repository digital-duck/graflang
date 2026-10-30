"""BATCH (design E5, map): a subgraph over a list, one value collected per item, items optionally at the same time."""
import time

import pytest

from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.topology import check
from test_lifecycle import Scripted


def batch_graph(**cfg):
    body = {"nodes": [{"id": "w", "type": "GENERATE", "ports": ["trigger", "complete", "in_item", "out_text"],
                       "config": {"prompt_inline": "do {{in_item}}"}}], "edges": []}
    batch = {"id": "b", "type": "BATCH", "ports": ["trigger", "exit", "in_items", "out_texts"],
             "config": {"subgraph": body, "outputs": {"texts": {"collect": "w.out_text"}}, **cfg}}
    return {"version": "1.0-graph", "resources": {}, "workflow": {"name": "t", "inputs": [{"name": "items", "type": "JSON"}],
            "outputs": [{"name": "texts", "type": "JSON"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_items"]}, batch,
                      {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_texts"]}],
            "edges": [{"source": "s.entry", "target": "b.trigger", "type": "triggers"},
                      {"source": "s.out_items", "target": "b.in_items", "type": "binds"},
                      {"source": "b.out_texts", "target": "o.in_texts", "type": "binds"},
                      {"source": "b.exit", "target": "o.trigger", "type": "triggers"}]}


class Echo(Scripted):
    def __init__(self, delay=0.0):
        super().__init__()
        self.delay = delay

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        time.sleep(self.delay)
        return prompt.upper()


def test_one_value_is_collected_per_item_in_order():
    llm = Echo()
    out = GraphLangRuntime(batch_graph(), llm=llm, verbose=False).execute({"items": ["a", "b", "c"]})
    assert out == {"texts": ["DO A", "DO B", "DO C"]}


def test_the_list_may_arrive_as_json_text_and_an_empty_list_gives_an_empty_result():
    assert GraphLangRuntime(batch_graph(), llm=Echo(), verbose=False).execute({"items": '["x"]'}) == {"texts": ["DO X"]}
    assert GraphLangRuntime(batch_graph(), llm=Echo(), verbose=False).execute({"items": []}) == {"texts": []}


def test_items_run_at_the_same_time_with_concurrency_and_keep_their_order():
    items = list("abcd")
    started = time.perf_counter()
    seq = GraphLangRuntime(batch_graph(), llm=Echo(0.2), verbose=False).execute({"items": items})
    t_seq = time.perf_counter() - started
    started = time.perf_counter()
    par = GraphLangRuntime(batch_graph(concurrency=4), llm=Echo(0.2), verbose=False).execute({"items": items})
    t_par = time.perf_counter() - started
    assert seq == par and t_seq >= 0.8 and t_par < 0.6, (t_seq, t_par)


def test_the_item_and_its_position_are_visible_to_the_body():
    g = batch_graph()
    g["nodes"][1]["config"]["subgraph"]["nodes"][0] = {"id": "w", "type": "SOLVE", "ports": ["trigger", "complete", "in_item", "in_index", "out_text"],
                                                       "config": {"expression": "str(@in_index) + ':' + @in_item"}}
    assert GraphLangRuntime(g, verbose=False).execute({"items": ["a", "b"]}) == {"texts": ["0:a", "1:b"]}


@pytest.mark.parametrize("cfg, items, message", [
    ({}, "not a list", "must hold a list"),
    ({"max_items": 2}, ["a", "b", "c"], "over max_items"),
])
def test_bad_input_is_named(cfg, items, message):
    with pytest.raises(ValueError, match=message):
        GraphLangRuntime(batch_graph(**cfg), llm=Echo(), verbose=False).execute({"items": items})


def test_validate_checks_the_batch():
    assert check(batch_graph())[0] == []
    g = batch_graph(concurrency=0, outputs={"texts": {"from": "w.out_text"}})
    errors = check(g)[0]
    assert any("concurrency must be" in m for m in errors) and any("must be {collect" in m for m in errors)
    g = batch_graph(outputs={"texts": {"collect": "ghost.out_text"}})
    assert any("no node 'ghost'" in m for m in check(g)[0])


@pytest.mark.llm
def test_real_llm_maps_a_list():
    """claude_cli (claude-sonnet-5-5): three short calls, two at a time."""
    g = batch_graph(concurrency=2)
    g["nodes"][1]["config"]["subgraph"]["nodes"][0]["config"]["prompt_inline"] = "Reply with only the English word for this color's name in uppercase: {{in_item}}"
    out = GraphLangRuntime(g, adapter="claude_cli", verbose=False).execute({"items": ["red", "green", "blue"]})
    assert [t.strip().upper().rstrip(".") for t in out["texts"]] == ["RED", "GREEN", "BLUE"]
