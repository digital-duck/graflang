"""cookbook_v2: recipes ported to the layered form (docs/DEV/DESIGN/graflang-recipes.md). Each one must validate with no errors or warnings, and
behave like the original in cookbook/ (same outputs, same steps run), checked offline with the echo and mock adapters."""
from pathlib import Path

import pytest

pytest.importorskip("spl", reason="procedure_ref nodes need SPL.py importable")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "cookbook_v2"
GRAPHS = sorted(p for p in V2.rglob("*.graph.yaml") if "output" not in p.parts)


@pytest.mark.parametrize("path", GRAPHS, ids=lambda p: str(p.relative_to(V2)))
def test_every_v2_graph_validates_with_no_errors_and_no_warnings(path):
    assert check(load_graph(path)) == ([], [])


# ---- code_pipeline ---------------------------------------------------------------------------------------------------------------

ORIGINAL = ROOT / "cookbook" / "code_pipeline" / "code_pipeline.graph.yaml"
LAYERED = V2 / "code_pipeline" / "code_pipeline.graph.yaml"
# the steps of the original and the node each became in the layered one (ids are `<composite>__<step>`)
SAME_STEPS = {"analyze": "understand__analyze", "spec_gate": "understand__clear", "document": "finish__document", "extract": "finish__extract",
              "closure_gate": "finish__closure", "judge": "finish__judge", "merge_docs": "finish__merge"}
LOOP_STEPS = {"loop_gen": "generate", "loop_rev": "review", "loop_imp": "improve", "loop_test": "test", "loop_eval": "ok", "loop_guard": "retry"}


def run(path, adapter, params, cwd, monkeypatch):
    monkeypatch.chdir(cwd)                                  # the procedures write their logs under the current folder
    rt = GraphLangRuntime(load_graph(path), llm=make_llm(adapter), verbose=False)
    return rt, rt.execute(params)


@pytest.mark.parametrize("params", [{"spec": "add two numbers", "max_cycles": 2, "check_closure": True},
                                    {"spec": "add two numbers", "max_cycles": 1, "check_closure": False}], ids=["with-closure-check", "without"])
def test_the_layered_pipeline_gives_the_same_output_and_runs_the_same_steps(params, tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    old, out_old = run(ORIGINAL, "echo", params, a, monkeypatch)
    new, out_new = run(LAYERED, "echo", params, b, monkeypatch)
    assert out_new == out_old and "docs" in out_new
    for before, after in SAME_STEPS.items():
        assert new.fired.get(after, 0) == old.fired.get(before, 0), (before, after)
    assert new.loop_iterations["build__attempts"] == old.loop_iterations["test_gated_loop"]


def test_a_vague_spec_stops_the_run_in_both_and_the_layered_one_names_the_cause(tmp_path, monkeypatch):
    """The mock adapter's analysis has no [READY]: the gate fails. The original aborts through its RECOVER node; the layered one leaves the
    `understand` composite by its `vague` error exit, which carries the code E_SPEC_VAGUE and its catalogue text."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    old, out_old = run(ORIGINAL, "mock", {"spec": "do things"}, a, monkeypatch)
    new, out_new = run(LAYERED, "mock", {"spec": "do things"}, b, monkeypatch)
    assert out_new == out_old and not out_new.get("docs")
    assert old.fired.get("test_gated_loop", 0) == 0 and new.loop_iterations.get("build__attempts", 0) == 0     # neither started building
    (exit_info,) = [x for x in load_graph(LAYERED)["_error_exits"] if x["code"] == "E_SPEC_VAGUE"]
    assert exit_info["use"] == "understand" and "too vague" in exit_info["description"] and exit_info["remedy"]


def test_the_layered_pipeline_reads_as_three_composites():
    from graphlang.grafv.model import build
    top, _ = build(load_graph(LAYERED), 0)
    names = {n for n in top.nodes}
    assert {"understand", "build", "finish"} <= names and top.number_of_nodes() <= 8          # the top level is a handful of nodes
    assert len(load_graph(LAYERED)["nodes"]) == len(load_graph(ORIGINAL)["nodes"])             # opened, the same graph (the loop body sits inside the loop node)
