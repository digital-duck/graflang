"""The interface of a composite: a level sees only a part's ports (neighbour rule), its description, and its named error exits."""
import shutil
from pathlib import Path

import pytest
import yaml

from graphlang.grafr.compact import expand
from graphlang.grafr.parts import PartError
from graphlang.grafr.runtime import load_graph
from graphlang.grafr.topology import check

DEMO = Path(__file__).resolve().parent.parent / "cookbook" / "parts_demo"


def demo(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
    return dst, expand(yaml.safe_load((dst / "parts_demo.graph.yaml").read_text()))


def test_an_edge_into_a_composites_inner_node_is_refused(tmp_path):
    dst, d = demo(tmp_path)
    d["nodes"].append({"id": "peek", "type": "OBSERVE", "ports": ["trigger", "complete", "in_x"]})
    d["edges"].append({"source": "first__rewrite.out_essay", "target": "peek.in_x", "type": "binds"})
    (dst / "x.graph.yaml").write_text(yaml.safe_dump(d))
    with pytest.raises(PartError, match="inside the composite 'first'"):
        load_graph(dst / "x.graph.yaml")


def test_the_same_wiring_through_the_ports_is_fine(tmp_path):
    dst, d = demo(tmp_path)
    assert check(load_graph(dst / "parts_demo.graph.yaml"))[0] == []


# ---- error exits ----------------------------------------------------------------------------------------------------

PART = """
version: "1.0-graph"
workflow:
  name: checker
  description: Passes a positive number on, refuses any other.
  inputs: [{name: n, type: INTEGER}]
  outputs: [{name: n, type: INTEGER}]
  errors: [{name: invalid, description: the number was not positive}]
nodes:
  - {id: wf_entry, type: INPUT, ports: [entry, out_n]}
  - {id: positive, type: EVALUATE, ports: [trigger, pass, fail, in_n], config: {condition: "@in_n > 0"}}
  - {id: keep, type: SOLVE, ports: [trigger, complete, in_n, out_v], config: {expression: "@in_n"}}
  - {id: ok, type: OUTPUT, ports: [trigger, exit, in_n]}
  - {id: bad, type: OUTPUT, ports: [trigger, exit], config: {exit: invalid}}
edges:
  - {source: wf_entry.entry, target: positive.trigger, type: triggers}
  - {source: wf_entry.out_n, target: positive.in_n, type: binds}
  - {source: positive.pass, target: keep.trigger, type: triggers}
  - {source: keep.complete, target: ok.trigger, type: triggers}
  - {source: positive.fail, target: bad.trigger, type: triggers}
  - {source: wf_entry.out_n, target: keep.in_n, type: binds}
  - {source: keep.out_v, target: ok.in_n, type: binds}
"""

PARENT = """
version: "1.0-graph"
workflow:
  name: use_checker
  inputs: [{name: n, type: INTEGER}]
  outputs: [{name: result, type: TEXT}]
resources: {parts: {checker: ./checker.graph.yaml}}
nodes:
  - {id: wf_entry, type: INPUT, ports: [entry, out_n]}
  - {id: chk, type: SUBGRAPH, ports: [trigger, complete, invalid, in_n, out_n], config: {part: parts.checker}}
  - {id: good, type: SOLVE, ports: [trigger, complete, out_r], config: {expression: "'accepted'"}}
  - {id: sorry, type: SOLVE, ports: [trigger, complete, out_r], config: {expression: "'refused'"}}
  - {id: done_ok, type: OUTPUT, ports: [trigger, exit, in_result]}
  - {id: done_bad, type: OUTPUT, ports: [trigger, exit, in_result]}
edges:
  - {source: wf_entry.entry, target: chk.trigger, type: triggers}
  - {source: wf_entry.out_n, target: chk.in_n, type: binds}
  - {source: chk.complete, target: good.trigger, type: triggers}
  - {source: chk.invalid, target: sorry.trigger, type: triggers}
  - {source: good.complete, target: done_ok.trigger, type: triggers}
  - {source: sorry.complete, target: done_bad.trigger, type: triggers}
  - {source: good.out_r, target: done_ok.in_result, type: binds}
  - {source: sorry.out_r, target: done_bad.in_result, type: binds}
"""


def run_checker(tmp_path, n, part=PART, parent=PARENT):
    from graphlang.grafr.runtime import GraphLangRuntime
    (tmp_path / "checker.graph.yaml").write_text(part)
    (tmp_path / "use.graph.yaml").write_text(parent)
    g = load_graph(tmp_path / "use.graph.yaml")
    return g, GraphLangRuntime(g, verbose=False).execute({"n": n})


def test_an_error_exit_routes_to_its_own_port_and_complete_does_not_fire(tmp_path):
    g, out = run_checker(tmp_path, 5)
    assert out == {"result": "accepted"} and check(g)[0] == []
    _, out = run_checker(tmp_path, -1)
    assert out == {"result": "refused"}


def test_an_undeclared_port_on_the_use_is_refused(tmp_path):
    with pytest.raises(PartError, match="not an error exit"):
        run_checker(tmp_path, 1, parent=PARENT.replace("invalid, in_n", "oops, in_n").replace("chk.invalid", "chk.oops"))


def test_an_output_that_names_an_undeclared_exit_is_refused(tmp_path):
    with pytest.raises(PartError, match="not declared in workflow.errors"):
        run_checker(tmp_path, 1, part=PART.replace("exit: invalid", "exit: weird"))


def test_a_declared_error_nothing_ends_is_refused(tmp_path):
    with pytest.raises(PartError, match="no OUTPUT node ends it"):
        run_checker(tmp_path, 1, part=PART.replace("{exit: invalid}", "{}"))


def test_error_exits_work_in_the_compact_form_and_survive_graf_compact(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    (tmp_path / "checker.graph.yaml").write_text(PART)
    app = tmp_path / "app.graph.yaml"
    app.write_text('''version: "1.0-graph"
workflow:
  name: app
  inputs: [{name: n, type: INTEGER}]
  outputs: [{name: result, type: TEXT}]
resources: {parts: {checker: ./checker.graph.yaml}}
steps:
  - chk: {use: parts.checker, in: {n: $in.n}, out: [n], ports: [invalid]}
  - good: {solve: "'accepted'", on: chk}
  - sorry: {solve: "'refused'", on: chk.invalid, out: r}
  - done: {output: {result: good.result}, on: good}
  - done2: {output: {result: sorry.r}, on: sorry}
''')
    from graphlang.grafr.runtime import GraphLangRuntime
    for n, want in ((4, "accepted"), (-3, "refused")):
        assert GraphLangRuntime(load_graph(app), verbose=False).execute({"n": n}) == {"result": want}
    r = CliRunner().invoke(main, ["compact", str(app), "-o", str(tmp_path / "again.graph.yaml")])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "again.graph.yaml").read_text()
    chk = next(s["chk"] for s in yaml.safe_load(text)["steps"] if "chk" in s)
    assert chk["ports"] == ["invalid"] and "on: chk.invalid" in text           # (PyYAML would read a bare `on:` key as True)


def test_graf_parts_shows_the_description_and_the_error_exits(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    (tmp_path / "checker.graph.yaml").write_text(PART)
    (tmp_path / "use.graph.yaml").write_text(PARENT)
    r = CliRunner().invoke(main, ["parts", str(tmp_path / "use.graph.yaml")])
    assert r.exit_code == 0, r.output
    assert "Passes a positive number on" in r.output and "can end in invalid (the number was not positive)" in r.output


def test_group_takes_a_description_into_the_interface():
    from graphlang.grafr.group import group
    from test_group import long_form
    _, part, _ = group(long_form(), ["b", "c"], "tail", "doubles, then adds ten")
    assert part["workflow"]["description"] == "doubles, then adds ten"
