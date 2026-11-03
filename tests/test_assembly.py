"""Assembly by a model (composability step 7): MUTATE `add_part` adds a recipe from the node's catalogue to the running graph,
under every rule a delta has (schema, Cedar, budget, invariants) and the workflow's `parts_policy`."""
import json
import shutil
from pathlib import Path

import pytest
import yaml

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

COOKBOOK = Path(__file__).resolve().parent.parent / "cookbook"


class Scripted:
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self, *rules):
        self.rules = list(rules)

    def generate(self, prompt, model=None, **opts):
        for needle, reply in self.rules:
            if needle in prompt:
                return reply
        raise AssertionError(f"no rule for prompt: {prompt[:100]!r}")


def build(tmp_path, catalogue=None, header=None):
    for r in ("guardrail", "agent_notes"):
        shutil.copytree(COOKBOOK / r, tmp_path / "catalogue" / r, ignore=shutil.ignore_patterns("output"))
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "mut.cedar").write_text("permit(principal, action, resource);\n")
    cat = catalogue if catalogue is not None else {"guardrail": "./catalogue/guardrail/guardrail.graph.yaml",
                                                   "agent_notes": "./catalogue/agent_notes/agent_notes.graph.yaml"}
    g = {"version": "1.0-graph",
         "workflow": {"name": "assembler", "inputs": [{"name": "question", "type": "TEXT"}, {"name": "delta", "type": "TEXT"}],
                      "outputs": [{"name": "reply", "type": "TEXT"}, {"name": "why", "type": "TEXT"}], **(header or {})},
         "resources": {"policies": {"mut": "./policies/mut.cedar"}},
         "nodes": [{"id": "wf_entry", "type": "INPUT", "ports": ["entry", "out_question", "out_delta"]},
                   {"id": "pick", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta", "out_reason"],
                    "config": {"policy_ref": "policies.mut", "catalogue": cat, "max_mutations": 2}},
                   {"id": "wf_exit", "type": "OUTPUT", "ports": ["trigger", "exit", "in_reply", "in_why"]}],
         "edges": [{"source": "wf_entry.entry", "target": "pick.trigger", "type": "triggers"},
                   {"source": "wf_entry.out_delta", "target": "pick.in_delta", "type": "binds"},
                   {"source": "pick.rejected", "target": "wf_exit.trigger", "type": "triggers"},
                   {"source": "pick.out_reason", "target": "wf_exit.in_why", "type": "binds"}]}
    path = tmp_path / "assembler.graph.yaml"
    path.write_text(yaml.safe_dump(g, sort_keys=False))
    return path


def add_guardrail(**over):
    payload = {"id": "g1", "part": "guardrail", "after": "pick.applied", "before": "wf_exit.trigger",
               "binds": {"question": "wf_entry.out_question"}, "feeds": {"reply": ["wf_exit.in_reply"]}, **over}
    return json.dumps({"action": "add_part", "payload": payload})


def run(path, llm, **params):
    graph = load_graph(path)
    errors, _ = check(graph)
    assert errors == [], errors
    return GraphLangRuntime(graph, llm=llm, verbose=False, effects=True).execute(params)


def test_a_model_adds_a_recipe_from_the_catalogue_and_it_runs(tmp_path):
    llm = Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "Pack layers."))
    out = run(build(tmp_path), llm, question="Iceland?", delta=add_guardrail())
    assert out["reply"] == "Pack layers."


def test_the_added_part_follows_the_graph_it_was_added_to(tmp_path):
    llm = Scripted(("guardrail for a travel advisor", "NO"), ("not about travel", "Travel only."))
    assert run(build(tmp_path), llm, question="linked list?", delta=add_guardrail())["reply"] == "Travel only."


@pytest.mark.parametrize("delta, why", [
    (add_guardrail(part="nonesuch"), "not in the catalogue"),
    (add_guardrail(id="pick"), "already exists"),
    (add_guardrail(binds={"question": "wf_entry.out_nope"}), "no port"),
    (add_guardrail(binds={}), "not bound"),
    (add_guardrail(binds={"question": "wf_entry.out_question", "bogus": "wf_entry.out_question"}), "not an input"),
])
def test_a_bad_assembly_is_rejected_and_nothing_is_added(tmp_path, delta, why):
    out = run(build(tmp_path), Scripted(), question="x", delta=delta)
    assert why in out["why"] and not out.get("reply")


def test_a_path_cannot_be_smuggled_in_as_a_part(tmp_path):
    out = run(build(tmp_path), Scripted(), question="x", delta=add_guardrail(part="../../etc/x"))
    assert "does not match the schema" in out["why"]


def test_the_workflow_can_forbid_what_a_model_may_add(tmp_path):
    path = build(tmp_path, header={"parts_policy": {"forbid": ["read"]}})
    out = run(path, Scripted(), question="x", delta=add_guardrail(part="agent_notes", binds={"question": "wf_entry.out_question"},
                                                                  feeds={"answer": ["wf_exit.in_reply"]}))
    assert "forbids" in out["why"]


def test_the_call_cap_applies_to_what_a_model_adds(tmp_path):
    path = build(tmp_path, header={"parts_policy": {"max_llm_calls": 2}})
    out = run(path, Scripted(), question="x", delta=add_guardrail())
    assert "max_llm_calls" in out["why"]


def test_a_delta_cannot_change_the_catalogue(tmp_path):
    delta = json.dumps({"action": "update_config", "payload": {"node_id": "pick", "key": "catalogue", "value": {"x": "/tmp/x"}}})
    out = run(build(tmp_path), Scripted(), question="x", delta=delta)
    assert out["why"] and not out.get("reply")
