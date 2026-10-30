"""Node lifecycle (pre -> exec -> post, design E1): retry, fallback, out_schema, and the validate checks."""
import pytest

from graphlang.grafr.lifecycle import check_phases
from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.topology import check

PROMPT = {"id": "g", "type": "GENERATE", "ports": ["trigger", "complete", "error", "in_topic", "out_text"]}
OUT = {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_text"]}
ENTRY = {"id": "s", "type": "INPUT", "ports": ["entry"]}


class Scripted:
    """An LLM that answers from a list, one reply per call, and records the prompts."""
    name = "scripted"
    model_override = None

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def graph(phases, extra_edges=()):
    node = {**PROMPT, "config": {"prompt_inline": "About {{in_topic}}", "phases": phases}}
    edges = [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
             {"source": "g.out_text", "target": "o.in_text", "type": "binds"},
             {"source": "g.complete", "target": "o.trigger", "type": "triggers"}, *extra_edges]
    return {"version": "1.0-graph", "resources": {}, "workflow": {"name": "t", "inputs": [], "outputs": [{"name": "text"}]},
            "nodes": [ENTRY, node, OUT], "edges": edges}


def run(phases, llm, **kw):
    rt = GraphLangRuntime(graph(phases, **kw), llm=llm, verbose=False)
    return rt, rt.execute({})


def test_a_transient_error_is_retried_then_succeeds():
    llm = Scripted(OSError("boom"), "ok")
    rt, out = run({"exec": {"retry": {"max": 1}}}, llm)
    assert out["text"] == "ok" and len(llm.prompts) == 2


def test_retries_are_bounded_and_the_last_error_surfaces():
    llm = Scripted(OSError("a"), OSError("b"))
    with pytest.raises(OSError, match="b"):
        run({"exec": {"retry": {"max": 1}}}, llm)


def test_a_permanent_error_is_not_retried():
    llm = Scripted(ValueError("bad config"), "never")
    with pytest.raises(ValueError):
        run({"exec": {"retry": {"max": 3}}}, llm)
    assert len(llm.prompts) == 1


def test_wait_between_attempts(monkeypatch):
    slept = []
    monkeypatch.setattr("graphlang.grafr.lifecycle.time.sleep", slept.append)
    run({"exec": {"retry": {"max": 1, "wait_s": 2}}}, Scripted(OSError("x"), "ok"))
    assert slept == [2.0]


def test_out_schema_parses_json_text_and_the_next_node_sees_data():
    schema = {"type": "object", "required": ["n"], "properties": {"n": {"type": "integer"}}}
    llm = Scripted('```json\n{"n": 3}\n```')
    rt, out = run({"post": {"out_schema": schema}}, llm)
    assert out["text"] == {"n": 3}
    assert "JSON Schema" in llm.prompts[0]                          # GENERATE asks for JSON matching the schema


def test_invalid_output_reprompts_with_the_validation_error():
    schema = {"type": "object", "required": ["n"]}
    llm = Scripted("not json", '{"n": 1}')
    rt, out = run({"exec": {"retry": {"max": 1, "on": ["invalid_output"]}}, "post": {"out_schema": schema}}, llm)
    assert out["text"] == {"n": 1}
    assert "rejected" in llm.prompts[1] and "not valid JSON" in llm.prompts[1]


def test_invalid_output_without_retry_fails_the_node():
    with pytest.raises(ValueError, match="required property"):
        run({"post": {"out_schema": {"type": "object", "required": ["n"]}}}, Scripted("{}"))


def test_fallback_value_flows_through_post():
    rt, out = run({"exec": {"fallback": {"value": '{"n": 0}'}}, "post": {"out_schema": {"type": "object"}}},
                  Scripted(ValueError("no")))
    assert out["text"] == {"n": 0}


def test_fallback_route_leaves_by_the_error_port():
    edges = [{"source": "g.error", "target": "o.trigger", "type": "triggers"}]
    rt, out = run({"exec": {"fallback": {"route": "error"}}}, Scripted(OSError("down")), extra_edges=edges)
    assert rt.fired.get("o") == 1                                   # reached OUTPUT through error, not complete
    assert ("g", "error") in rt.emitted and ("g", "complete") not in rt.emitted


def test_pre_fills_defaults_and_requires_inputs():
    llm = Scripted("a")
    run({"pre": {"defaults": {"in_topic": "cats"}}}, llm)
    assert "About cats" in llm.prompts[0]
    with pytest.raises(ValueError, match="required input"):
        run({"pre": {"require": ["in_topic"]}}, Scripted("a"))


def test_a_node_without_phases_runs_as_before():
    node = {**PROMPT, "config": {"prompt_inline": "x"}}
    rt = GraphLangRuntime({**graph({}), "nodes": [ENTRY, node, OUT]}, llm=Scripted("plain"), verbose=False)
    assert rt.execute({})["text"] == "plain"


@pytest.mark.parametrize("phases, fragment", [
    ({"pretend": {}}, "unknown phase"),
    ({"exec": {"retry": {"max": -1}}}, "whole number"),
    ({"exec": {"retry": {"on": ["permanent"]}}}, "never retried"),
    ({"exec": {"fallback": {"route": "nope"}}}, "not a port"),
    ({"exec": {"fallback": {"route": "error", "value": 1}}}, "exactly one"),
    ({"pre": {"require": ["in_nope"]}}, "not an in_* port"),
    ({"post": {"out_schema": {"type": "bogus"}}}, "not a JSON Schema"),
    ({"exec": {"timeout": 5}}, "unknown key"),
])
def test_validate_reports_bad_phases(phases, fragment):
    node = {**PROMPT, "config": {"prompt_inline": "x", "phases": phases}}
    assert any(fragment in m for m in check_phases(node)), check_phases(node)
    assert any(fragment in m for m in check(graph(phases))[0])


def test_validate_accepts_good_phases():
    good = {"pre": {"require": ["in_topic"]}, "exec": {"retry": {"max": 2, "wait_s": 1, "on": ["transient", "invalid_output"]},
            "fallback": {"route": "error"}}, "post": {"out_schema": {"type": "object"}}}
    assert check_phases({**PROMPT, "config": {"phases": good}}) == []


@pytest.mark.llm
def test_real_llm_returns_json_matching_the_schema():
    """claude_cli (default model claude-sonnet-5-5), one short call."""
    schema = {"type": "object", "required": ["capital"], "properties": {"capital": {"type": "string"}}}
    g = graph({"exec": {"retry": {"max": 1, "on": ["invalid_output"]}}, "post": {"out_schema": schema}})
    g["nodes"][1]["config"]["prompt_inline"] = "What is the capital of France?"
    out = GraphLangRuntime(g, adapter="claude_cli", verbose=False).execute({})
    assert "paris" in out["text"]["capital"].lower()


# ---- timeout, post route, RECOVER ------------------------------------------------------------------------------------

def test_a_slow_attempt_times_out_and_is_retried():
    import time

    class Slow(Scripted):
        def generate(self, prompt, model=None, **opts):
            if not self.prompts:
                self.prompts.append(prompt)
                time.sleep(2)
            return super().generate(prompt, model, **opts) if self.replies else "late"

    llm = Slow("fast")
    rt, out = run({"exec": {"timeout_s": 0.2, "retry": {"max": 1}}}, llm)
    assert out["text"] == "fast"


def test_a_timeout_without_retry_fails():
    import time

    class Slow(Scripted):
        def generate(self, prompt, model=None, **opts):
            time.sleep(2)

    with pytest.raises(TimeoutError):
        run({"exec": {"timeout_s": 0.1}}, Slow())


def test_post_route_picks_the_port_from_the_result():
    edges = [{"source": "g.empty", "target": "o.trigger", "type": "triggers"}]
    node_ports = PROMPT["ports"] + ["empty"]
    g = graph({"post": {"route": {"empty": "@out_text == ''"}}}, extra_edges=edges)
    g["nodes"][1]["ports"] = node_ports
    rt = GraphLangRuntime(g, llm=Scripted(""), verbose=False)
    rt.execute({})
    assert ("g", "empty") in rt.emitted and ("g", "complete") not in rt.emitted
    rt = GraphLangRuntime(g, llm=Scripted("full"), verbose=False)
    rt.execute({})
    assert ("g", "complete") in rt.emitted


def recover_graph(**cfg):
    """g fails (fallback route error) -> r (RECOVER); `retry` loops back to g."""
    g = graph({"exec": {"fallback": {"route": "error"}}})
    g["nodes"].append({"id": "r", "type": "RECOVER", "ports": ["trigger", "retry", "complete", "in_error", "out_error"], "config": cfg})
    g["edges"] += [{"source": "g.error", "target": "r.trigger", "type": "triggers"},
                   {"source": "g.out_text", "target": "r.in_error", "type": "binds"},
                   {"source": "r.retry", "target": "g.trigger", "type": "triggers"}]
    return g


def test_recover_retry_sends_the_token_back_then_gives_up():
    llm = Scripted(OSError("1"), OSError("2"), OSError("3"))
    rt = GraphLangRuntime(recover_graph(action="retry", max_retries=1, then="halt"), llm=llm, verbose=False)
    rt.execute({})
    assert rt.fired["g"] == 2 and rt.fired["r"] == 2                # one retry, then halt
    assert ("r", "complete") not in rt.emitted


def test_recover_retry_ends_in_success():
    rt = GraphLangRuntime(recover_graph(action="retry", max_retries=2), llm=Scripted(OSError("1"), "fine"), verbose=False)
    assert rt.execute({})["text"] == "fine"


def test_recover_abort_fails_the_run_and_skip_carries_on():
    with pytest.raises(RuntimeError, match="aborted the run: stop"):
        GraphLangRuntime(recover_graph(action="abort", message="stop"), llm=Scripted(OSError("x")), verbose=False).execute({})
    rt = GraphLangRuntime(recover_graph(action="skip"), llm=Scripted(OSError("x")), verbose=False)
    rt.execute({})
    assert ("r", "complete") in rt.emitted


def test_recover_checks_in_validate():
    g = recover_graph(action="retry")
    g["nodes"][-1]["ports"].remove("retry")
    g["edges"].pop()
    assert any("needs a 'retry' port" in m for m in check(g)[0])
    assert any("action must be" in m for m in check(recover_graph(action="explode"))[0])
    assert not any("RECOVER" in m for m in check(recover_graph(action="retry", then="halt"))[0])


@pytest.mark.parametrize("phases, fragment", [
    ({"exec": {"timeout_s": 0}}, "timeout_s"),
    ({"post": {"route": {"nope": "@out_text"}}}, "not a control port"),
    ({"post": {"route": {"error": "@out_zzz"}}}, "not an in_* or out_* port"),
])
def test_validate_reports_bad_timeout_and_route(phases, fragment):
    assert any(fragment in m for m in check_phases({**PROMPT, "config": {"phases": phases}})), phases
