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


# ---- error codes: optional, but one code names one cause ---------------------------------------------------------------

def catalogue(folder, *codes, text=None):
    """A graflang.errors.yaml beside the graph defining `codes` (each with a description and a remedy)."""
    entries = "".join(f"  - {{code: {c}, description: {c} happened, remedy: fix {c}}}\n" for c in codes)
    (folder / "graflang.errors.yaml").write_text(text if text is not None else f"errors:\n{entries}")


CODED = PART.replace("{name: invalid, description:", "{name: invalid, code: E_NOT_POSITIVE, description:")


def test_the_code_of_a_taken_exit_is_logged_with_the_failure(tmp_path):
    import json
    from click.testing import CliRunner
    from graphlang.cli import main
    (tmp_path / "checker.graph.yaml").write_text(CODED)
    (tmp_path / "use.graph.yaml").write_text(PARENT)
    catalogue(tmp_path, "E_NOT_POSITIVE")
    logs = tmp_path / "logs"

    def events(n):
        for f in logs.glob("*.jsonl") if logs.exists() else []:
            f.unlink()
        r = CliRunner().invoke(main, ["run", str(tmp_path / "use.graph.yaml"), "--param", f"n={n}", "--log-dir", str(logs), "--log-format", "jsonl",
                                      "--no-output"])
        assert r.exit_code == 0, r.output
        return [json.loads(line) for f in logs.glob("*.jsonl") for line in f.read_text().splitlines() if '"part.error"' in line]
    assert events(5) == []                                                    # the normal way out logs nothing
    (hit,) = events(-1)
    assert (hit["use"], hit["part"], hit["error"], hit["code"]) == ("chk", "checker", "invalid", "E_NOT_POSITIVE")
    assert hit["description"] == "E_NOT_POSITIVE happened" and hit["remedy"] == "fix E_NOT_POSITIVE"       # the catalogue's text travels with it


def test_a_bad_code_and_a_repeated_code_in_one_part_are_refused(tmp_path):
    with pytest.raises(PartError, match="must be letters"):
        run_checker(tmp_path, 1, part=PART.replace("{name: invalid, description:", "{name: invalid, code: '9 bad', description:"))
    two = PART.replace("errors: [{name: invalid, description: the number was not positive}]",
                       "errors: [{name: invalid, code: E1, description: a}, {name: other, code: E1, description: b}]")
    two = two.replace('''  - {id: bad, type: OUTPUT, ports: [trigger, exit], config: {exit: invalid}}''', '''  - {id: bad, type: OUTPUT, ports: [trigger, exit], config: {exit: invalid}}
  - {id: bad2, type: OUTPUT, ports: [trigger, exit], config: {exit: other}}''')
    with pytest.raises(PartError, match="more than one error"):
        run_checker(tmp_path, 1, part=two)


def _two_parts(tmp_path, other_code):
    (tmp_path / "checker.graph.yaml").write_text(CODED)
    (tmp_path / "second.graph.yaml").write_text(CODED.replace("name: checker", "name: second").replace("E_NOT_POSITIVE", other_code))
    parent = PARENT.replace("resources: {parts: {checker: ./checker.graph.yaml}}",
                            "resources: {parts: {checker: ./checker.graph.yaml, second: ./second.graph.yaml}}")
    parent = parent.replace("  - {id: good,", '''  - {id: chk2, type: SUBGRAPH, ports: [trigger, complete, invalid, in_n, out_n], config: {part: parts.second}}
  - {id: good,''').replace("  - {source: wf_entry.out_n, target: chk.in_n, type: binds}", '''  - {source: wf_entry.out_n, target: chk.in_n, type: binds}
  - {source: chk.complete, target: chk2.trigger, type: triggers}
  - {source: wf_entry.out_n, target: chk2.in_n, type: binds}
  - {source: chk2.invalid, target: sorry.trigger, type: triggers}''').replace("{source: chk.complete, target: good.trigger, type: triggers}", "{source: chk2.complete, target: good.trigger, type: triggers}")
    (tmp_path / "use.graph.yaml").write_text(parent)
    catalogue(tmp_path, "E_NOT_POSITIVE", other_code)
    return tmp_path / "use.graph.yaml"


def test_the_same_code_in_two_different_parts_of_one_graph_is_refused(tmp_path):
    with pytest.raises(PartError, match="declared by both"):
        load_graph(_two_parts(tmp_path, "E_NOT_POSITIVE"))


def test_different_codes_in_two_parts_are_fine(tmp_path):
    g = load_graph(_two_parts(tmp_path, "E_SECOND"))
    assert {x["code"] for x in g["_error_exits"]} == {"E_NOT_POSITIVE", "E_SECOND"}


def test_one_part_used_twice_keeps_its_code_and_the_use_path_tells_the_copies_apart(tmp_path):
    use = _two_parts(tmp_path, "E_SECOND")
    use.write_text(use.read_text().replace("./second.graph.yaml", "./checker.graph.yaml"))       # `second` is now the same file as `checker`
    g = load_graph(use)
    assert sorted((x["use"], x["code"]) for x in g["_error_exits"]) == [("chk", "E_NOT_POSITIVE"), ("chk2", "E_NOT_POSITIVE")]


# ---- the catalogue: graflang.errors.yaml ----------------------------------------------------------------------------------

def test_a_code_that_the_catalogue_does_not_define_is_refused(tmp_path):
    (tmp_path / "checker.graph.yaml").write_text(CODED)
    (tmp_path / "use.graph.yaml").write_text(PARENT)
    with pytest.raises(PartError, match="not defined in graflang.errors.yaml"):
        load_graph(tmp_path / "use.graph.yaml")
    catalogue(tmp_path, "E_NOT_POSITIVE")
    assert check(load_graph(tmp_path / "use.graph.yaml"))[0] == []


def test_a_graph_with_no_codes_needs_no_catalogue(tmp_path):
    g, out = run_checker(tmp_path, 5)
    assert out == {"result": "accepted"}


def test_a_code_defined_twice_or_in_both_the_shipped_and_the_local_file_is_refused(tmp_path, monkeypatch):
    from graphlang.grafr import errors_catalogue as ec
    (tmp_path / "checker.graph.yaml").write_text(CODED)
    (tmp_path / "use.graph.yaml").write_text(PARENT)
    catalogue(tmp_path, "E_NOT_POSITIVE", "E_NOT_POSITIVE")
    with pytest.raises(PartError, match="defined twice"):
        load_graph(tmp_path / "use.graph.yaml")
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    catalogue(shipped, "E_NOT_POSITIVE")
    monkeypatch.setattr(ec, "SHIPPED", shipped / "graflang.errors.yaml")
    catalogue(tmp_path, "E_NOT_POSITIVE")
    with pytest.raises(PartError, match="also defined in the shipped catalogue"):
        load_graph(tmp_path / "use.graph.yaml")


def test_a_malformed_catalogue_says_what_is_wrong(tmp_path):
    from graphlang.grafr.errors_catalogue import CatalogueError, load
    for text, why in (("errors:\n  - {code: '9x', description: d}\n", "needs a `code`"), ("errors:\n  - {code: E1}\n", "needs a one-line `description`"),
                      ("errors:\n  - {code: E1, description: d, colour: red}\n", "unknown keys"), ("nope: 1\n", "top-level `errors:`")):
        catalogue(tmp_path, text=text)
        with pytest.raises(CatalogueError, match=why):
            load(tmp_path / "graflang.errors.yaml")


def test_graf_errors_lists_and_looks_up_codes(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    catalogue(tmp_path, text="errors:\n  - {code: E_A, description: a happened, cause: because, remedy: do b}\n")
    r = CliRunner().invoke(main, ["errors", "--dir", str(tmp_path)])
    assert r.exit_code == 0 and "E_A: a happened" in r.output
    r = CliRunner().invoke(main, ["errors", "E_A", "--dir", str(tmp_path)])
    assert r.exit_code == 0 and "cause: because" in r.output and "remedy: do b" in r.output
    assert CliRunner().invoke(main, ["errors", "E_NOPE", "--dir", str(tmp_path)]).exit_code == 1


def test_the_shipped_catalogue_loads():
    from graphlang.grafr.errors_catalogue import SHIPPED, load
    assert SHIPPED.is_file() and isinstance(load(SHIPPED), dict)


# ---- inherits: pass a key of the level above down without writing the binding ---------------------------------------------------

def inherit_app(tmp_path, inherits="[n]", part_type="INTEGER", top_type="INTEGER", extra="", also=""):
    (tmp_path / "checker.graph.yaml").write_text(PART.replace("inputs: [{name: n, type: INTEGER}]", f"inputs: [{{name: n, type: {part_type}}}]"))
    app = tmp_path / "app.graph.yaml"
    app.write_text(f'''version: "1.0-graph"
workflow:
  name: app
  inputs: [{{name: n, type: {top_type}}}{also}]
  outputs: [{{name: result, type: TEXT}}]
resources: {{parts: {{checker: ./checker.graph.yaml}}}}
steps:
  - chk: {{use: parts.checker, inherits: {inherits}, out: [n], ports: [invalid]{extra}}}
  - good: {{solve: "'accepted'", on: chk}}
  - sorry: {{solve: "'refused'", on: chk.invalid, out: r}}
  - done: {{output: {{result: good.result}}, on: good}}
  - done2: {{output: {{result: sorry.r}}, on: sorry}}
''')
    return app


def test_inherits_passes_the_levels_input_down_like_an_explicit_in(tmp_path):
    from graphlang.grafr.runtime import GraphLangRuntime
    g = load_graph(inherit_app(tmp_path))
    assert GraphLangRuntime(g, verbose=False).execute({"n": 4}) == {"result": "accepted"}
    assert GraphLangRuntime(load_graph(tmp_path / "app.graph.yaml"), verbose=False).execute({"n": -1}) == {"result": "refused"}


def test_inherits_survives_graf_compact_and_expands_the_same(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    app = inherit_app(tmp_path)
    r = CliRunner().invoke(main, ["compact", str(app), "-o", str(tmp_path / "again.graph.yaml")])
    assert r.exit_code == 0, r.output
    a, b = load_graph(app), load_graph(tmp_path / "again.graph.yaml")
    key = lambda e: (e["source"], e["target"], e["type"])      # noqa: E731
    assert sorted(map(key, a["edges"])) == sorted(map(key, b["edges"]))


def test_inherits_a_name_the_part_does_not_declare_or_a_type_that_does_not_fit_is_refused(tmp_path):
    from graphlang.grafr.compact import CompactError
    with pytest.raises(CompactError, match="not a workflow input"):                        # the level above has no such input
        load_graph(inherit_app(tmp_path, inherits="[n, budget]"))
    with pytest.raises(PartError, match="is not an input of the part"):                  # the level above has it, the part does not
        load_graph(inherit_app(tmp_path, inherits="[n, budget]", also=", {name: budget, type: TEXT}"))
    with pytest.raises(PartError, match="has TEXT but the part declares INTEGER"):
        load_graph(inherit_app(tmp_path, top_type="TEXT"))
    assert load_graph(inherit_app(tmp_path, part_type="FLOAT", top_type="INTEGER"))        # an INTEGER fits a FLOAT input: the part's type is the one that counts


def test_inherits_and_in_that_disagree_are_refused(tmp_path):
    from graphlang.grafr.compact import CompactError
    with pytest.raises(CompactError, match="already gives it another value"):
        load_graph(inherit_app(tmp_path, extra=", in: {n: sorry}"))
