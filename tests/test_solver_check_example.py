"""cookbook/solver_check: a kernel solver and a black-box subprocess solver compute the same sum; an ASSERT compares both with
the expected value. No LLM; needs `pip install 'graflang[kernel]'`."""
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph

pytestmark = pytest.mark.skipif(find_spec("jupyter_client") is None or find_spec("ipykernel") is None,
                                reason="needs graflang[kernel]")

GRAPH = Path(__file__).resolve().parent.parent / "cookbook" / "solver_check" / "solver_check.graph.yaml"


def run(numbers, expected, mutate=None):
    data = load_graph(GRAPH)
    if mutate:
        mutate(data)
    runtime = GraphLangRuntime(data, verbose=False)
    return runtime, runtime.execute({"numbers": numbers, "expected": expected})


def test_both_solvers_agree_with_the_expected_value():
    runtime, out = run("1,2,3", 6)
    assert out == {"verdict": "confirmed: 6 (kernel and subprocess agree)"}
    assert "report_ok" in runtime.fired and "report_mismatch" not in runtime.fired


def test_a_wrong_expected_value_is_a_mismatch():
    runtime, out = run("1,2,3", 7)
    assert out == {"verdict": "MISMATCH: kernel 6, subprocess 6, expected 7"}
    assert "report_ok" not in runtime.fired


def test_a_failing_subprocess_routes_to_the_error_report_instead_of_ending_the_run():
    def break_the_script(data):
        node = next(n for n in data["nodes"] if n["id"] == "sum_script")
        node["config"]["command"] = [sys.executable, "-I", "-c", "import sys; sys.exit(2)"]
    runtime, out = run("1,2,3", 6, break_the_script)
    assert out["verdict"].startswith("solver failed: solver exited 2")
    assert "agree" not in runtime.fired


def test_a_parser_that_cannot_read_the_output_fails_closed():
    def silent_script(data):
        node = next(n for n in data["nodes"] if n["id"] == "sum_script")
        node["config"]["command"] = [sys.executable, "-I", "-c", "print('nothing useful')"]
    _, out = run("1,2,3", 6, silent_script)
    assert "no 'total: N' line" in out["verdict"]
