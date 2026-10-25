"""The subprocess solver backend (graphlang/grafr/solver.py), standalone: no graph, no LLM. Commands are Python one-liners."""
import sys
from pathlib import Path

import pytest

from graphlang.grafr.solver import (SolverError, check_type, parse_first_line, parse_last_json, parse_regex, read_output,
                                    run_solver)

PY = [sys.executable, "-I", "-c"]


def solver(code: str, **kw):
    kw.setdefault("parse", "last_json")
    kw.setdefault("out_type", "JSON")
    kw.setdefault("base_dir", Path("."))
    return run_solver(PY + [code], {"a": 2, "b": 3}, **kw)


def test_inputs_arrive_as_json_on_stdin_and_the_last_json_on_stdout_is_the_value():
    code = "import json,sys; d=json.load(sys.stdin); print('working...'); print(json.dumps({'sum': d['a'] + d['b']}))"
    res = solver(code, out_type="JSON")
    assert res.value == {"sum": 5} and res.returncode == 0 and "working" in res.stdout and res.parser == "last_json"


def test_a_fenced_json_block_is_accepted():
    code = "print('here it is:'); print('```json\\n{\"ok\": true}\\n```')"
    assert solver(code, out_type="JSON").value == {"ok": True}


def test_first_line_with_declared_tokens_for_a_sat_style_solver():
    code = "import sys; sys.stdin.read(); print('sat'); print('x = 1')"
    res = solver(code, parse={"first_line": ["sat", "unsat"]}, out_type="TEXT")
    assert res.value == "sat"


def test_regex_with_a_named_group():
    code = "import sys; sys.stdin.read(); print('result: 42 units')"
    # the regex yields text; turning "42" into a number is a custom parser's job, not a guess
    assert solver(code, parse={"regex": r"result: (?P<value>\d+)"}, out_type="TEXT").value == "42"
    with pytest.raises(SolverError, match="expected INTEGER"):
        solver(code, parse={"regex": r"result: (?P<value>\d+)"}, out_type="INTEGER")


def test_a_value_of_the_wrong_type_is_a_failure_with_the_raw_output_kept():
    code = "import sys; sys.stdin.read(); print('maybe')"
    with pytest.raises(SolverError) as e:
        solver(code, parse={"first_line": ["yes", "no"]}, out_type="BOOL")
    assert "output not accepted" in str(e.value) and "maybe" in e.value.stdout


def test_no_parser_match_is_a_failure_and_nothing_is_guessed():
    with pytest.raises(SolverError):
        solver("import sys; sys.stdin.read(); print('no json here')", out_type="JSON")


def test_non_zero_exit_keeps_stdout_and_stderr():
    with pytest.raises(SolverError) as e:
        solver("import sys; sys.stdin.read(); print('partial'); sys.stderr.write('boom\\n'); sys.exit(3)")
    assert e.value.returncode == 3 and "partial" in e.value.stdout and "boom" in e.value.stderr


def test_a_timeout_is_a_failure():
    with pytest.raises(SolverError, match="timed out"):
        solver("import time; time.sleep(30)", timeout=1)


def test_a_missing_command_is_a_failure_not_a_crash():
    with pytest.raises(SolverError, match="not found"):
        run_solver(["no-such-solver-xyz"], {}, parse="last_json", out_type="JSON", base_dir=Path("."))


def test_a_custom_parser_is_loaded_from_the_graph_folder(tmp_path):
    (tmp_path / "parsers.py").write_text(
        "def z3_result(stdout):\n    return stdout.split()[0] == 'sat'\n", encoding="utf-8")
    code = "import sys; sys.stdin.read(); print('sat model: x=1')"
    res = run_solver(PY + [code], {}, parse={"tool": "parsers.py:z3_result"}, out_type="BOOL", base_dir=tmp_path)
    assert res.value is True and res.parser == "tool parsers.py:z3_result"


def test_a_custom_parser_that_raises_is_a_solver_error_with_the_raw_output(tmp_path):
    (tmp_path / "parsers.py").write_text("def broken(stdout):\n    raise KeyError('model')\n", encoding="utf-8")
    with pytest.raises(SolverError, match="output not accepted") as e:
        run_solver(PY + ["import sys; sys.stdin.read(); print('raw text')"], {}, parse={"tool": "parsers.py:broken"},
                   out_type="TEXT", base_dir=tmp_path)
    assert "raw text" in e.value.stdout


def test_a_custom_parser_naming_a_missing_file_or_function_is_reported(tmp_path):
    with pytest.raises(SolverError):
        run_solver(PY + ["print(1)"], {}, parse={"tool": "missing.py:f"}, out_type="INTEGER", base_dir=tmp_path)
    (tmp_path / "p.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SolverError):
        run_solver(PY + ["print(1)"], {}, parse={"tool": "p.py:f"}, out_type="INTEGER", base_dir=tmp_path)


def test_an_unknown_parser_declaration_is_rejected():
    with pytest.raises(ValueError, match="unknown parser"):
        read_output({"nonsense": 1}, "x", Path("."))


def test_type_checks():
    assert check_type(True, "BOOL") is True
    assert check_type(3, "REAL") == 3 and check_type(3, "INTEGER") == 3
    for value, kind in [(True, "INTEGER"), ("3", "INTEGER"), (1, "BOOL"), (None, "TEXT")]:
        with pytest.raises(ValueError):
            check_type(value, kind)
    with pytest.raises(ValueError, match="unknown output type"):
        check_type(1, "FLOAT")


def test_the_built_in_parsers_on_their_own():
    assert parse_last_json('noise {"a": 1} more\n[1, 2]') == [1, 2]
    assert parse_last_json("nothing") is None
    assert parse_first_line("  \nSAT\nmodel") == "SAT" and parse_first_line("", None) is None
    assert parse_first_line("maybe", ["sat"]) is None
    assert parse_regex("x=7", r"x=(\d)") == "7" and parse_regex("nope", r"x=(\d)") is None
