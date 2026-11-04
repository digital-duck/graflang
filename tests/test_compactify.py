"""`graf compact`: the inverse of `graf expand`, kept exact by re-expanding and comparing."""
import glob
import json

import pytest
from ruamel.yaml import YAML
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.compact import expand
from graphlang.grafr.compactify import NotCompactable, compactify


def _load(text_or_file):
    return YAML(typ="safe").load(text_or_file)


def _canon(g):
    nodes = {n["id"]: json.dumps({**n, "ports": sorted(n["ports"])}, sort_keys=True) for n in g["nodes"]}
    return nodes, {json.dumps(e, sort_keys=True) for e in g.get("edges", [])}


GRAPHS = sorted(glob.glob("cookbook/*/*.graph.yaml"))


@pytest.mark.parametrize("path", GRAPHS)
def test_cookbook_round_trip(path):
    data = _load(open(path))
    try:
        long = expand(data) if "steps" in data else data
        out, report = compactify(data)
    except NotCompactable:
        pytest.skip("not a form steps: can say")
    back = expand(out)
    assert _canon(back)[0].keys() == _canon(long)[0].keys()
    assert _canon(back) == _canon(long)
    assert report["steps"] >= 1


def test_self_refine_is_fully_compact():
    out, report = compactify(_load(open("cookbook/self_refine/self_refine.graph.yaml")))
    assert report["nodes_kept"] == 0 and report["edges_kept"] == 0
    assert [next(iter(s)) for s in out["steps"]][0] == "draft"
    assert "nodes" not in out and "edges" not in out


def test_compact_expand_compact_is_stable():
    data = _load(open("cookbook/guardrail/guardrail.graph.yaml"))
    once, _ = compactify(data)
    twice, _ = compactify(once)
    assert once["steps"] == twice["steps"]


def test_odd_node_stays_long_and_result_is_exact():
    data = _load(open("cookbook/self_refine/self_refine.graph.yaml"))
    long = data
    long["nodes"].append({"id": "odd", "type": "RECOVER", "ports": ["halt", "in_message"], "config": {"action": "halt"}})
    long["edges"].append({"source": "draft.complete", "target": "odd.trigger", "type": "triggers"})
    out, report = compactify(long)
    assert report["nodes_kept"] == 1
    assert [n["id"] for n in out["nodes"]] == ["odd"]
    assert _canon(expand(out)) == _canon(long)


def test_back_edge_is_kept_as_edge():
    data = _load(open("cookbook/self_refine/self_refine.graph.yaml"))
    long = data
    first, last = long["nodes"][1]["id"], long["nodes"][-2]["id"]
    long["edges"].append({"source": f"{last}.complete", "target": f"{first}.trigger", "type": "triggers"})
    out, _ = compactify(long)
    assert _canon(expand(out)) == _canon(long)


def test_needs_entry_node():
    with pytest.raises(NotCompactable):
        compactify({"workflow": {"name": "x", "inputs": [], "outputs": []}, "nodes": [], "edges": []})


def test_cli(tmp_path):
    src = tmp_path / "g.graph.yaml"
    src.write_text(open("cookbook/self_refine/self_refine.graph.yaml").read())
    (tmp_path / "prompts").mkdir()
    out = tmp_path / "c.graph.yaml"
    res = CliRunner().invoke(main, ["compact", str(src), "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert "steps" in _load(out.read_text())


def test_alternatives_and_run_code_round_trip():
    text = """version: 1.0-graph
workflow: {name: t, inputs: [{name: m, type: TEXT}], outputs: [{name: r, type: TEXT}]}
steps:
  - gate: {evaluate: "@in_m == 'a'", in: {m: $in.m}}
  - one: {solve: "'print(1)'", on: gate.pass, out: program}
  - two: {solve: "'print(2)'", on: gate.fail, out: program}
  - ok: {guard: policies.p, on: [one, two], principal: 'Service::"x"', action: 'Action::"y"', resource: 'File::"z"', context_mapping: {}}
  - run: {run_code: [python], on: ok.allow, in: {language: "python", text: [one.program, two.program]}}
  - done: {output: run.output}
resources: {policies: {p: ./p.cedar}}
"""
    data = _load(text)
    long = expand(data)
    assert sum(1 for e in long["edges"] if e["target"] == "run.in_text") == 2       # both writers are wired
    node = next(n for n in long["nodes"] if n["id"] == "run")
    assert node["type"] == "RUN_CODE" and node["config"]["languages"] == ["python"] and "out_ran" in node["ports"]
    out, report = compactify(long)
    run_step = next(s["run"] for s in out["steps"] if "run" in s)
    assert run_step["run_code"] == ["python"] and run_step["in"]["text"] == ["one", "two"] and "out" not in run_step
    assert _canon(expand(out)) == _canon(long)
