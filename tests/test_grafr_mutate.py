"""Cedar enforcement (GUARD), self-revision (MUTATE) and the policies in graphlang/policies."""
import json
from pathlib import Path

import pytest

from graphlang.grafr.cedar_guard import CedarGuard, PolicyError, entity_uid
from graphlang.grafr.nodes import _EXECUTORS, register_executor
from graphlang.grafr.nodes.base import NodeExecutor
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

ROOT = Path(__file__).parent.parent
POLICY = ROOT / "graphlang" / "policies" / "mutation_safety.cedar"


@pytest.fixture(autouse=True)
def _restore_executors():
    saved = dict(_EXECUTORS)
    yield
    _EXECUTORS.clear()
    _EXECUTORS.update(saved)


# ---- Cedar -------------------------------------------------------------------------------------------

def test_entity_ids_are_normalised():
    assert entity_uid('Action::allow_retry') == 'Action::"allow_retry"'
    assert entity_uid('Service::"llm-agent"') == 'Service::"llm-agent"'
    with pytest.raises(ValueError):
        entity_uid("no-type-here")


def test_invalid_policy_text_is_rejected():
    with pytest.raises(PolicyError, match="not valid Cedar"):
        CedarGuard().load_policy("p", "permit(principal action resource)")


def test_default_deny_and_forbid_beats_permit():
    g = CedarGuard()
    g.load_policy("p", '''permit(principal, action, resource);
                          forbid(principal, action == Action::"x", resource) when { context.bad == true };''')
    assert g.decide("p", 'U::"a"', 'Action::"y"', 'R::"r"', {"bad": True}).allowed
    d = g.decide("p", 'U::"a"', 'Action::"x"', 'R::"r"', {"bad": True})
    assert not d.allowed and "denied by" in d.explain()
    g.load_policy("empty", '// no policies')
    assert not g.decide("empty", 'U::"a"', 'Action::"y"', 'R::"r"', {}).allowed          # default deny


def test_a_policy_that_errors_denies_instead_of_being_skipped():
    """Cedar skips a forbid that errors (here: reads a missing attribute) and the permit-all then allows it.
    The guard must treat the error as a deny."""
    g = CedarGuard()
    g.load_policy("p", '''forbid(principal, action, resource) when { context.nope == 1 };
                          permit(principal, action, resource);''')
    d = g.decide("p", 'U::"a"', 'Action::"y"', 'R::"r"', {})
    assert not d.allowed and d.errors and "evaluation error" in d.explain()


def test_shipped_mutation_policy_decisions():
    g = CedarGuard()
    g.load_policy("m", POLICY.read_text())

    def ask(cedar_action="mutate_graph", **delta):
        base = {"action": "add_node", "node_id": "", "node_type": "", "source_port": "", "target_port": "",
                "source": {"id": "", "type": "", "port": ""}, "target": {"id": "", "type": "", "port": ""}, **delta}
        ctx = {"proposed_delta": base, "mutation_count": 0, "max_allowed_mutations": 3,
               "human_approval": False, "contains_pii": False}
        return g.decide("m", 'Service::"llm-agent"', f'Action::"{cedar_action}"', 'Graph::"execution_topology"', ctx)

    assert ask(node_type="RECOVER").allowed
    d = ask(node_type="GENERATE")
    assert not d.allowed and d.reasons == ["policy5"]                             # forbidden: needs human approval
    assert not ask(**{"action": "remove_node", "node_type": "ASSERT"}).allowed
    assert ask(**{"action": "remove_node", "node_type": "SOLVE"}).reasons == ["policy0"]      # forbid, not default deny
    d = ask(**{"action": "remove_node", "node_type": "EVALUATE"})
    assert not d.allowed and d.reasons == [] and d.errors == []                   # nothing permits it: default deny
    assert ask(**{"action": "remove_edge", "source_port": "ASSERT.fail"}).reasons == ["policy1"]
    assert ask(**{"action": "add_edge", "target_port": "RECOVER.trigger"}).allowed
    assert not ask(**{"action": "add_edge", "target_port": "GENERATE.trigger"}).allowed
    d = ask("allow_retry")                                                        # context lacks cycle/max_cycles
    assert not d.allowed and d.errors                                             # the error denies (fail closed)


# ---- GUARD -------------------------------------------------------------------------------------------

def graph(nodes, edges, inputs=(), outputs=(), resources=None):
    g = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": list(inputs), "outputs": list(outputs)},
         "nodes": nodes, "edges": edges}
    if resources:
        g["resources"] = resources
        g["_source_dir"] = str(ROOT)
    return g


def trig(a, b):
    return {"source": a, "target": b, "type": "triggers"}


def bind(a, b):
    return {"source": a, "target": b, "type": "binds"}


RES = {"policies": {"m": "graphlang/policies/mutation_safety.cedar"}}


class Probe(NodeExecutor):
    def __init__(self):
        self.calls = 0

    def execute(self, node_data, in_data, context, resolver, llm):
        self.calls += 1
        return {}


def guard_graph(cycle, max_cycles):
    return graph(
        [{"id": "start", "type": "INPUT", "ports": ["entry", "out_c", "out_m"]},
         {"id": "gd", "type": "GUARD", "ports": ["trigger", "allow", "deny", "in_cycle", "in_max_cycles"],
          "config": {"policy_ref": "policies.m", "action": 'Action::"allow_retry"',
                     "context_mapping": {"cycle": "@in_cycle", "max_cycles": "@in_max_cycles"}}},
         {"id": "yes", "type": "OBSERVE", "ports": ["trigger", "complete"]},
         {"id": "no", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
        [trig("start.entry", "gd.trigger"), trig("gd.allow", "yes.trigger"), trig("gd.deny", "no.trigger"),
         bind("start.out_c", "gd.in_cycle"), bind("start.out_m", "gd.in_max_cycles")],
        inputs=[{"name": "c", "type": "INTEGER"}, {"name": "m", "type": "INTEGER"}], resources=RES)


def test_guard_allows_and_denies_through_cedar():
    rt = GraphLangRuntime(guard_graph(1, 3), verbose=False)
    rt.execute({"c": 1, "m": 3})
    assert "yes" in rt.fired and "no" not in rt.fired
    rt = GraphLangRuntime(guard_graph(3, 3), verbose=False)
    rt.execute({"c": 3, "m": 3})
    assert "no" in rt.fired and "yes" not in rt.fired


def test_guard_without_a_policy_or_with_a_bad_mapping_is_an_error_not_an_allow():
    g = guard_graph(0, 1)
    del g["nodes"][1]["config"]["policy_ref"]
    with pytest.raises(ValueError, match="no config.policy_ref"):
        GraphLangRuntime(g, verbose=False).execute({"c": 0, "m": 1})
    g = guard_graph(0, 1)
    g["nodes"][1]["config"]["context_mapping"] = {"cycle": "@nope"}
    with pytest.raises(ValueError, match="context_mapping.*unknown variable @nope"):
        GraphLangRuntime(g, verbose=False).execute({"c": 0, "m": 1})


def test_flagship_loop_is_governed_by_the_guard():
    data = load_graph(ROOT / "cookbook" / "code_pipeline" / "code_pipeline.graph.yaml")

    def prompts(nodes):
        for n in nodes:
            if n.get("config", {}).get("procedure_ref"):
                n["config"] = {"prompt_inline": "do {{in_spec}}"}
            if "subgraph" in n.get("config", {}):
                prompts(n["config"]["subgraph"]["nodes"])

    prompts(data["nodes"])

    class Failing(NodeExecutor):
        def execute(self, node_data, in_data, context, resolver, llm):
            return {"out_result": "[FAILED]"}

    class Echo:
        name, model_override = "fake", None

        def generate(self, prompt, model=None, **o):
            return "[READY]"

    register_executor("SOLVE", Failing())
    rt = GraphLangRuntime(data, llm=Echo(), verbose=False)
    out = rt.execute({"spec": "s", "max_cycles": 3, "check_closure": False})
    assert rt.loop_iterations == {"test_gated_loop": 3} and "docs" in out        # tests never pass: ran to the budget


# ---- MUTATE ------------------------------------------------------------------------------------------

def mutate_graph(delta, **cfg):
    config = {"policy_ref": "policies.m", **cfg}
    return graph(
        [{"id": "start", "type": "INPUT", "ports": ["entry", "out_d"]},
         {"id": "mut", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta", "out_reason"],
          "config": config},
         {"id": "after", "type": "OBSERVE", "ports": ["trigger", "complete"]},
         {"id": "refused", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
        [trig("start.entry", "mut.trigger"), trig("mut.applied", "after.trigger"), trig("mut.rejected", "refused.trigger"),
         bind("start.out_d", "mut.in_delta")],
        inputs=[{"name": "d", "type": "TEXT"}], resources=RES)


def run(delta, **cfg):
    rt = GraphLangRuntime(mutate_graph(delta, **cfg), verbose=False)
    rt.execute({"d": delta})
    return rt, ("applied" if "after" in rt.fired else "rejected" if "refused" in rt.fired else "neither"), \
        rt.values.get(("mut", "out_reason"))


ADD_RECOVER = {"action": "add_node", "payload": {"id": "rec", "type": "RECOVER", "ports": ["trigger", "halt"]}}


def test_an_allowed_delta_is_applied_to_the_live_graph():
    rt, outcome, reason = run(ADD_RECOVER)
    assert outcome == "applied" and "rec" in rt.G and rt.G.nodes["rec"]["type"] == "RECOVER"
    assert reason.startswith("add_node") and rt.budget.mutations == 1


def test_json_text_and_code_fences_are_accepted():
    rt, outcome, _ = run("```json\n" + json.dumps(ADD_RECOVER) + "\n```")
    assert outcome == "applied" and "rec" in rt.G
    rt, outcome, _ = run(json.dumps(ADD_RECOVER))
    assert outcome == "applied"


def test_mutation_changes_where_later_tokens_go():
    """Two MUTATE nodes in a row: the first adds a node, the second wires its own `applied` port to it, and the
    token it sends afterwards follows the new edge."""
    wire = {"action": "add_edge", "payload": {"source": "mut2.applied", "target": "rec.trigger", "type": "triggers"}}
    marks = Probe()
    register_executor("RECOVER", marks)
    g = graph([{"id": "start", "type": "INPUT", "ports": ["entry", "out_a", "out_b"]},
               {"id": "mut1", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta"],
                "config": {"policy_ref": "policies.m"}},
               {"id": "mut2", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta"],
                "config": {"policy_ref": "policies.m"}}],
              [trig("start.entry", "mut1.trigger"), trig("mut1.applied", "mut2.trigger"),
               bind("start.out_a", "mut1.in_delta"), bind("start.out_b", "mut2.in_delta")],
              inputs=[{"name": "a", "type": "TEXT"}, {"name": "b", "type": "TEXT"}], resources=RES)
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"a": json.dumps(ADD_RECOVER), "b": json.dumps(wire)})
    assert rt.fired.get("rec") == 1 and marks.calls == 1 and rt.budget.mutations == 2


@pytest.mark.parametrize("delta, why", [
    ("not json", "not valid JSON"),
    ('[1, 2]', "must be a JSON object"),
    ({"action": "explode", "payload": {}}, "schema"),
    ({"action": "add_node", "payload": {"id": "x y", "type": "RECOVER", "ports": ["trigger"]}}, "schema"),
    ({"action": "add_node", "payload": {"id": "rec", "type": "MUTATE", "ports": ["trigger"]}}, "schema"),       # cannot add MUTATE
    ({"action": "add_node", "payload": {"id": "mut", "type": "RECOVER", "ports": ["trigger"]}}, "already exists"),
    ({"action": "remove_node", "payload": {"id": "ghost"}}, "no node 'ghost'"),
    ({"action": "remove_node", "payload": {"id": "start"}}, "cannot be removed"),
    ({"action": "add_edge", "payload": {"source": "ghost.complete", "target": "after.trigger", "type": "triggers"}}, "no node 'ghost'"),
    ({"action": "add_edge", "payload": {"source": "after.nope", "target": "refused.trigger", "type": "triggers"}}, "no port 'nope'"),
    ({"action": "add_edge", "payload": {"source": "after.complete", "target": "refused.complete", "type": "triggers"}}, "trigger port"),
    ({"action": "add_edge", "payload": {"source": "after.complete", "target": "refused.trigger", "type": "binds"}}, "out_ port to an in_"),
    ({"action": "add_edge", "payload": {"source": "mut.applied", "target": "after.trigger", "type": "triggers"}}, "already exists"),
    ({"action": "remove_edge", "payload": {"source": "after.complete", "target": "refused.trigger", "type": "triggers"}}, "no such edge"),
    ({"action": "update_config", "payload": {"node_id": "after", "key": "type", "value": "GENERATE"}}, "cannot be changed"),
    ({"action": "update_config", "payload": {"node_id": "ghost", "key": "k", "value": 1}}, "no node"),
])
def test_bad_deltas_are_rejected_with_a_reason_and_change_nothing(delta, why):
    rt, outcome, reason = run(delta)
    assert outcome == "rejected" and why in reason, reason
    assert rt.budget.mutations == 0 and set(rt.G.nodes) == {"start", "mut", "after", "refused"}


def test_cedar_refusals_are_rejections_too():
    generate = {"action": "add_node", "payload": {"id": "g", "type": "GENERATE", "ports": ["trigger", "complete"]}}
    rt, outcome, reason = run(generate)
    assert outcome == "rejected" and "denied by" in reason and "g" not in rt.G           # needs human approval
    rt, outcome, _ = run(generate, human_approval=True)
    assert outcome == "rejected"                                                          # approved, but nothing permits GENERATE: default deny
    remove_assert = {"action": "remove_node", "payload": {"id": "mut"}}
    assert run(remove_assert)[1] == "rejected"                                            # no permit for remove_node at all


def test_the_mutation_budget_is_enforced_by_policy():
    rt, outcome, _ = run(ADD_RECOVER, max_mutations=0)
    assert outcome == "rejected" and "rec" not in rt.G


def test_mutate_is_deny_by_default_and_must_declare_its_routes():
    g = mutate_graph(ADD_RECOVER)
    del g["nodes"][1]["config"]["policy_ref"]
    with pytest.raises(ValueError, match="deny-by-default"):
        GraphLangRuntime(g, verbose=False).execute({"d": "{}"})
    g = mutate_graph(ADD_RECOVER)
    g["nodes"][1]["ports"] = ["trigger", "in_delta"]
    g["edges"] = [e for e in g["edges"] if not e["source"].startswith("mut.")]          # (the runtime rejects edges to missing ports)
    with pytest.raises(ValueError, match="must declare the ports"):
        GraphLangRuntime(g, verbose=False).execute({"d": "{}"})
    g = mutate_graph(ADD_RECOVER)
    del g["edges"][-1]                                                                    # nothing feeds in_delta
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"d": "x"})
    assert "refused" in rt.fired and "no delta" in rt.values[("mut", "out_reason")]


# ---- the safety layer and the invariants a mutation must keep ---------------------------------------------

def guarded_graph(delta, **cfg):
    """start -> gd -allow-> act (risky); gd -deny-> refused. The MUTATE runs first, from the INPUT's entry port."""
    return graph(
        [{"id": "start", "type": "INPUT", "ports": ["entry", "out_d"]},
         {"id": "mut", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta", "out_reason"],
          "config": {"policy_ref": "policies.m", **cfg}},
         {"id": "gd", "type": "GUARD", "ports": ["trigger", "allow", "deny"], "config": {"policy_ref": "policies.g"}},
         {"id": "act", "type": "OBSERVE", "ports": ["trigger", "complete"], "config": {"risky": True}},
         {"id": "refused", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
        [trig("start.entry", "mut.trigger"), trig("mut.applied", "gd.trigger"), trig("mut.rejected", "refused.trigger"),
         trig("gd.allow", "act.trigger"), bind("start.out_d", "mut.in_delta")],
        inputs=[{"name": "d", "type": "TEXT"}], resources={**RES, "policies": {**RES["policies"], "g": RES["policies"]["m"]}})


def run_guarded(delta):
    rt = GraphLangRuntime(guarded_graph(delta), verbose=False)
    rt.execute({"d": json.dumps(delta)})
    return rt, rt.values.get(("mut", "out_reason")), "refused" in rt.fired


@pytest.mark.parametrize("delta, why", [
    ({"action": "remove_node", "payload": {"id": "gd"}}, "cannot be removed"),
    ({"action": "update_config", "payload": {"node_id": "gd", "key": "policy_ref", "value": "policies.m"}}, "safety layer"),
    ({"action": "update_config", "payload": {"node_id": "mut", "key": "max_mutations", "value": 99}}, "safety layer"),
    ({"action": "update_config", "payload": {"node_id": "act", "key": "risky", "value": False}}, "safety layer"),
])
def test_a_delta_cannot_touch_the_safety_layer(delta, why):
    rt, reason, refused = run_guarded(delta)
    assert refused and why in reason, reason
    assert rt.G.nodes["act"]["config"]["risky"] is True and "gd" in rt.G


def test_a_delta_that_routes_around_a_guard_is_rejected_by_the_graph_check_even_if_the_policy_permits_it(tmp_path):
    (tmp_path / "all.cedar").write_text("permit(principal, action, resource);\n")
    around = {"action": "add_edge", "payload": {"source": "mut.applied", "target": "act.trigger", "type": "triggers"}}
    g = guarded_graph(around)
    g["resources"]["policies"]["m"] = "all.cedar"
    g["_source_dir"] = str(tmp_path)
    rt = GraphLangRuntime(g, verbose=False)
    rt.execute({"d": json.dumps(around)})
    reason = rt.values.get(("mut", "out_reason"))
    assert "refused" in rt.fired and "would break the graph" in reason and "'act'" in reason, reason
    assert rt.budget.mutations == 0
