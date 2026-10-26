"""SOLVE backends in a running graph: `kernel` (a Python kernel) and `subprocess` (a black-box program), the checks `graf validate`
runs on them, and the rule that a MUTATE delta can never add or change what runs. The subprocess backend alone is covered in
test_solver_backend.py; the kernel tests need `pip install 'graflang[kernel]'`."""
import sys
import time
from importlib.util import find_spec
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.solve_backend import CODE_KEYS, SolveError, check_solve, code_keys_in
from graphlang.grafr.topology import check

ROOT = Path(__file__).parent.parent
needs_kernel = pytest.mark.skipif(find_spec("jupyter_client") is None or find_spec("ipykernel") is None,
                                  reason="needs graflang[kernel]")


def trig(a, b):
    return {"source": a, "target": b, "type": "triggers"}


def bind(a, b):
    return {"source": a, "target": b, "type": "binds"}


def build(steps, inputs=None):
    """start -> each SOLVE in turn -> end. `steps` are (id, config, extra ports); a workflow input is bound to every
    step that has an `in_<name>` port. The last step's `out_result` is the workflow's `result`."""
    inputs = inputs or {}
    nodes = [{"id": "start", "type": "INPUT", "ports": ["entry"] + [f"out_{n}" for n in inputs]},
             {"id": "end", "type": "OUTPUT", "ports": ["trigger", "exit", "in_result"]}]
    edges, previous = [], "start.entry"
    for sid, config, extra in steps:
        ports = ["trigger", "complete", "out_result"] + list(extra)
        nodes.append({"id": sid, "type": "SOLVE", "config": config, "ports": ports})
        edges.append(trig(previous, f"{sid}.trigger"))
        edges += [bind(f"start.out_{p[3:]}", f"{sid}.{p}") for p in ports if p.startswith("in_") and p[3:] in inputs]
        previous = f"{sid}.complete"
    edges += [trig(previous, "end.trigger"), bind(f"{steps[-1][0]}.out_result", "end.in_result")]
    return {"version": "1.0-graph",
            "workflow": {"name": "t", "inputs": [{"name": n, "type": "JSON"} for n in inputs],
                         "outputs": [{"name": "result", "type": "JSON"}]},
            "nodes": nodes, "edges": edges, "_source_dir": str(ROOT)}


def run(steps, inputs=None):
    runtime = GraphLangRuntime(build(steps, inputs), verbose=False)
    return runtime, runtime.execute(inputs or {})


PY = [sys.executable, "-I", "-c"]
SUM_SCRIPT = ("import json,sys; d=json.load(sys.stdin); t=sum(d['values']); "
              "print(json.dumps({'sum': t, 'equal': t == d['expected']}))")
KERNEL_SUM = {"backend": "kernel", "code": "total = sum(values)", "result": "{'sum': total, 'equal': total == expected}"}
SUBPROCESS_SUM = {"backend": "subprocess", "command": PY + [SUM_SCRIPT]}


# ---- running ------------------------------------------------------------------------------------------------------

@needs_kernel
def test_a_kernel_node_computes_over_bound_values_and_returns_json():
    _, out = run([("s", {"backend": "kernel", "code": "total = sum(values)", "result": "total", "out_type": "INTEGER"},
                   ["in_values"])], {"values": [1, 2, 3]})
    assert out == {"result": 6}


@needs_kernel
def test_the_same_graph_gives_the_same_result_with_either_backend():
    inputs = {"values": [1, 2, 3], "expected": 6}
    ports = ["in_values", "in_expected"]
    _, from_kernel = run([("s", KERNEL_SUM, ports)], inputs)
    _, from_subprocess = run([("s", SUBPROCESS_SUM, ports)], inputs)
    assert from_kernel == from_subprocess == {"result": {"sum": 6, "equal": True}}


@needs_kernel
def test_bound_values_are_data_never_code():
    hostile = "'); __import__('os').system('touch /tmp/graflang-pwned'); ('"
    _, out = run([("s", {"backend": "kernel", "code": "shown = note", "result": "shown"}, ["in_note"])], {"note": hostile})
    assert out == {"result": hostile}
    assert not Path("/tmp/graflang-pwned").exists()


@needs_kernel
def test_an_exception_fails_the_run_or_routes_to_the_error_port():
    boom = {"backend": "kernel", "code": "1 / 0", "result": "1"}
    with pytest.raises(SolveError, match="ZeroDivisionError"):
        run([("s", boom, [])])
    routed = build([("s", {**boom, "on_error": "route"}, ["error", "out_error"])])
    routed["nodes"].append({"id": "caught", "type": "OBSERVE", "ports": ["trigger", "complete"]})
    routed["edges"].append(trig("s.error", "caught.trigger"))
    runtime = GraphLangRuntime(routed, verbose=False)
    runtime.execute({})
    assert "caught" in runtime.fired and "end" not in runtime.fired
    assert "ZeroDivisionError" in runtime.values[("s", "out_error")]


@needs_kernel
def test_a_timeout_fails_within_the_configured_time():
    started = time.monotonic()
    with pytest.raises(SolveError, match="timed out"):
        run([("s", {"backend": "kernel", "code": "while True: pass", "result": "1", "timeout": 2}, [])])
    assert time.monotonic() - started < 30


@needs_kernel
def test_scope_run_keeps_a_variable_across_nodes_and_scope_node_does_not():
    first = {"backend": "kernel", "code": "counter = 41", "result": "counter"}
    second = {"backend": "kernel", "code": "counter += 1", "result": "counter"}
    assert run([("a", first, []), ("b", second, [])])[1] == {"result": 42}
    with pytest.raises(SolveError, match="NameError"):
        run([("a", {**first, "scope": "node"}, []), ("b", {**second, "scope": "node"}, [])])


@needs_kernel
def test_two_runs_do_not_share_variables():
    run([("a", {"backend": "kernel", "code": "leak = 1", "result": "leak"}, [])])
    _, out = run([("b", {"backend": "kernel", "code": "", "result": "'leak' in globals()"}, [])])
    assert out == {"result": False}


def test_a_failing_subprocess_fails_the_node_or_routes():
    bad = {"backend": "subprocess", "command": PY + ["import sys; sys.exit(3)"]}
    with pytest.raises(SolveError, match="exited 3"):
        run([("s", bad, [])])
    routed = build([("s", {**bad, "on_error": "route"}, ["error", "out_error"])])
    routed["nodes"].append({"id": "caught", "type": "OBSERVE", "ports": ["trigger", "complete"]})
    routed["edges"].append(trig("s.error", "caught.trigger"))
    runtime = GraphLangRuntime(routed, verbose=False)
    runtime.execute({})
    assert "caught" in runtime.fired and "exited 3" in runtime.values[("s", "out_error")]


def test_a_subprocess_result_of_the_wrong_type_fails_the_node():
    wrong = {"backend": "subprocess", "command": PY + ["print('{\"a\": 1}')"], "out_type": "BOOL"}
    with pytest.raises(SolveError, match="expected BOOL"):
        run([("s", wrong, [])])


def test_a_solve_with_no_computation_is_an_error_at_run_time_too():
    with pytest.raises(ValueError, match="computes nothing"):
        run([("s", {}, [])])


# ---- graf validate ------------------------------------------------------------------------------------------------

def solve(config, ports=("trigger", "complete", "out_result")):
    return {"id": "s", "type": "SOLVE", "config": config, "ports": list(ports)}


def problems(config, ports=("trigger", "complete", "out_result"), base_dir=ROOT):
    return check_solve(solve(config, ports), base_dir)


def test_a_solve_with_nothing_to_compute_is_a_validation_error():
    errors, _ = problems({"label": "x"})
    assert errors and "computes nothing" in errors[0]


def test_graf_validate_reports_backend_errors_through_the_topology_check():
    g = build([("s", {"backend": "kernel", "code": "x = (", "result": "1"}, [])])
    errors, _ = check(g)
    assert any("SOLVE 's'" in e and "syntax error" in e for e in errors)


@pytest.mark.parametrize("config, ports, text", [
    ({"backend": "kernel", "code": "x = (", "result": "1"}, ("trigger", "out_r"), "syntax error"),
    ({"backend": "kernel", "code": "x = 1", "result": "x +"}, ("trigger", "out_r"), "syntax error"),
    ({"backend": "kernel", "code": "x = 1"}, ("trigger", "out_r"), "needs `code` and `result`"),
    ({"backend": "kernel", "code": "x = 1", "result": "x", "scope": "forever"}, ("trigger", "out_r"), "scope must be"),
    ({"backend": "kernel", "code": "x = 1", "result": "x"}, ("trigger",), "exactly one result port"),
    ({"backend": "kernel", "code": "x = 1", "result": "x"}, ("trigger", "out_a", "out_b"), "exactly one result port"),
    ({"backend": "kernel", "code": "x = 1", "result": "x", "on_error": "route"}, ("trigger", "out_r"), "needs an 'error' port"),
    ({"backend": "kernel", "code": "x = 1", "result": "x", "timeout": 0}, ("trigger", "out_r"), "timeout must be"),
    ({"backend": "kernel", "code": "x = 1", "result": "x", "out_type": "COMPLEX"}, ("trigger", "out_r"), "unknown out_type"),
    ({"backend": "kernel", "code": "x = 1", "result": "x", "expression": "1"}, ("trigger", "out_r"), "cannot also have expression"),
    ({"backend": "teleport"}, ("trigger", "out_r"), "unknown backend"),
    ({"backend": "subprocess"}, ("trigger", "out_r"), "needs `command`"),
    ({"backend": "subprocess", "command": "python x.py"}, ("trigger", "out_r"), "needs `command`"),
    ({"backend": "subprocess", "command": ["x"], "parse": "magic"}, ("trigger", "out_r"), "unknown parser"),
    ({"backend": "subprocess", "command": ["x"], "parse": {"regex": "("}}, ("trigger", "out_r"), "does not compile"),
    ({"backend": "subprocess", "command": ["x"], "parse": {"tool": "nocolon"}}, ("trigger", "out_r"), "file.py:function"),
])
def test_backend_configuration_errors(config, ports, text):
    errors, _ = problems(config, ports)
    assert any(text in e for e in errors), errors


def test_an_input_the_code_never_uses_is_a_warning():
    _, warnings = problems({"backend": "kernel", "code": "x = a", "result": "x"},
                           ("trigger", "in_a", "in_b", "out_r"))
    assert any("in_b" in w and "never used" in w for w in warnings)
    assert not any("in_a" in w for w in warnings)


def test_things_the_user_supplies_are_warnings_not_errors(tmp_path):
    (tmp_path / "parsers.py").write_text("def other(s):\n    return s\n", encoding="utf-8")
    config = {"backend": "subprocess", "command": ["no-such-solver-xyz"], "parse": {"tool": "parsers.py:z3_result"},
              "requirements": ["no_such_requirement_xyz"]}
    errors, warnings = problems(config, base_dir=tmp_path)
    assert errors == []
    text = " | ".join(warnings)
    assert "no-such-solver-xyz" in text and "does not define a function 'z3_result'" in text and "no_such_requirement_xyz" in text
    errors, warnings = problems({**config, "parse": {"tool": "missing.py:f"}}, base_dir=tmp_path)
    assert errors == [] and any("was not found next to the graph" in w for w in warnings)


def test_validation_never_runs_a_custom_parser(tmp_path):
    marker = tmp_path / "ran"
    (tmp_path / "parsers.py").write_text(f"open({str(marker)!r}, 'w').write('x')\ndef f(s):\n    return s\n", encoding="utf-8")
    problems({"backend": "subprocess", "command": ["x"], "parse": {"tool": "parsers.py:f"}}, base_dir=tmp_path)
    assert not marker.exists()


# ---- MUTATE may not add code --------------------------------------------------------------------------------------

POLICY = {"policies": {"m": "graphlang/policies/mutation_safety.cedar"}}


def mutate_run(delta):
    g = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [{"name": "d", "type": "JSON"}], "outputs": []},
         "nodes": [{"id": "start", "type": "INPUT", "ports": ["entry", "out_d"]},
                   {"id": "mut", "type": "MUTATE", "ports": ["trigger", "applied", "rejected", "in_delta", "out_reason"],
                    "config": {"policy_ref": "policies.m"}},
                   {"id": "after", "type": "OBSERVE", "ports": ["trigger", "complete"]},
                   {"id": "refused", "type": "OBSERVE", "ports": ["trigger", "complete"]}],
         "edges": [trig("start.entry", "mut.trigger"), trig("mut.applied", "after.trigger"),
                   trig("mut.rejected", "refused.trigger"), bind("start.out_d", "mut.in_delta")],
         "resources": POLICY, "_source_dir": str(ROOT)}
    runtime = GraphLangRuntime(g, verbose=False)
    runtime.execute({"d": delta})
    return runtime, ("applied" if "after" in runtime.fired else "rejected"), runtime.values.get(("mut", "out_reason"))


def add_node(config):
    return {"action": "add_node", "payload": {"id": "extra", "type": "SOLVE", "ports": ["trigger", "complete", "out_r"],
                                              "config": config}}


def test_a_delta_without_code_keys_is_unaffected():
    delta = {"action": "add_node", "payload": {"id": "extra", "type": "RECOVER", "ports": ["trigger", "halt"],
                                               "config": {"label": "x"}}}
    runtime, verdict, _ = mutate_run(delta)
    assert verdict == "applied" and "extra" in runtime.G


@pytest.mark.parametrize("config", [
    {"backend": "subprocess", "command": ["rm", "-rf", "/tmp/x"]},
    {"backend": "kernel", "code": "import os", "result": "1"},
    {"expression": "1", "parse": {"tool": "evil.py:f"}},
])
def test_a_delta_cannot_add_a_node_that_runs_code(config):
    runtime, verdict, reason = mutate_run(add_node(config))
    assert verdict == "rejected" and "extra" not in runtime.G and "graph file" in reason


def test_a_delta_cannot_change_what_a_node_runs():
    for key in sorted(CODE_KEYS):
        runtime, verdict, reason = mutate_run({"action": "update_config",
                                               "payload": {"node_id": "after", "key": key, "value": "x"}})
        assert verdict == "rejected" and key in reason
        assert key not in runtime.G.nodes["after"].get("config", {})


def test_code_cannot_be_smuggled_in_a_nested_value():
    nested = {"nodes": [{"id": "w", "type": "SOLVE", "config": {"backend": "subprocess", "command": ["x"]}, "ports": ["trigger"]}]}
    runtime, verdict, _ = mutate_run({"action": "update_config",
                                      "payload": {"node_id": "after", "key": "subgraph", "value": nested}})
    assert verdict == "rejected" and "subgraph" not in runtime.G.nodes["after"].get("config", {})
    assert code_keys_in({"a": [{"b": {"command": 1}}], "code": 2}) == ["code", "command"]
    assert code_keys_in({"expression": "1", "label": "x"}) == []
