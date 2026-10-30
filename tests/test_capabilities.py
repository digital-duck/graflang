"""A workflow's own rules (design E8): `workflow.policy` is a Cedar policy about which nodes it may contain."""
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from graphlang.cli import main
from graphlang.grafr.topology import check

POLICY = Path(__file__).parent.parent / "graphlang" / "policies" / "capabilities.cedar"


def graph(tmp_path, node_cfg, node_type="SOLVE", policy=True, in_loop=False):
    (tmp_path / "caps.cedar").write_text(POLICY.read_text())
    node = {"id": "n", "type": node_type, "config": node_cfg, "ports": ["trigger", "complete", "out_v"]}
    nodes = [{"id": "s", "type": "INPUT", "ports": ["entry"]}, node]
    edges = [{"source": "s.entry", "target": "n.trigger", "type": "triggers"}]
    if in_loop:
        loop = {"id": "lp", "type": "LOOP", "ports": ["trigger", "exit"], "config": {"max_iterations": 1, "subgraph": {"nodes": [node], "edges": []}}}
        nodes, edges = [nodes[0], loop], [{"source": "s.entry", "target": "lp.trigger", "type": "triggers"}]
    return {"version": "1.0-graph", "_source_dir": str(tmp_path), "resources": {"policies": {"caps": "./caps.cedar"}},
            "workflow": {"name": "t", "inputs": [], "outputs": [], **({"policy": "policies.caps"} if policy else {})},
            "nodes": nodes, "edges": edges}


def denied(g):
    return [m for m in check(g)[0] if "not allowed by" in m]


def test_a_plain_node_is_allowed(tmp_path):
    assert denied(graph(tmp_path, {"expression": "1"})) == []


@pytest.mark.parametrize("needs", [["shell"], ["network"], ["fs_write"]])
def test_a_node_that_needs_a_capability_must_be_risky(tmp_path, needs):
    msgs = denied(graph(tmp_path, {"expression": "1", "needs": needs}))
    assert len(msgs) == 1 and "SOLVE 'n'" in msgs[0] and "policies.caps" in msgs[0]
    ok = denied(graph(tmp_path, {"expression": "1", "needs": needs, "risky": True}))
    assert (ok == []) == (needs != ["shell"])                         # shell is forbidden outright


def test_an_http_run_may_only_call_the_allowed_hosts(tmp_path):
    cfg = {"executor": "http", "url": "https://api.example.com/x", "allow_hosts": ["api.example.com"]}
    assert denied(graph(tmp_path, cfg, "RUN")) == []
    other = {"executor": "http", "url": "https://evil.example.net/x", "allow_hosts": ["evil.example.net"]}
    assert len(denied(graph(tmp_path, other, "RUN"))) == 1


def test_nodes_inside_a_loop_body_are_checked_too(tmp_path):
    msgs = denied(graph(tmp_path, {"expression": "1", "needs": ["shell"]}, in_loop=True))
    assert len(msgs) == 1 and "'lp/n'" in msgs[0]


def test_a_workflow_without_a_policy_is_not_checked(tmp_path):
    assert denied(graph(tmp_path, {"expression": "1", "needs": ["shell"]}, policy=False)) == []


def test_a_missing_policy_is_reported(tmp_path):
    g = graph(tmp_path, {"expression": "1"})
    (tmp_path / "caps.cedar").unlink()
    assert any("workflow policy" in m for m in check(g)[0])


def test_graf_run_refuses_a_graph_the_policy_denies(tmp_path):
    g = graph(tmp_path, {"expression": "1", "needs": ["shell"]})
    g.pop("_source_dir")
    g["workflow"]["outputs"] = []
    path = tmp_path / "w.graph.yaml"
    YAML().dump(g, path)
    result = CliRunner().invoke(main, ["run", str(path), "--adapter", "mock", "--no-log", "--no-output"])
    assert result.exit_code == 1 and "nothing was run" in result.output and "not allowed by" in result.output
