"""RUN_CODE: run the program a step produced; never fail the graph; prose is not run as code."""
import shutil

import pytest

from graphlang.grafr.run_code import check_run_code, code_of, run_code


def test_a_fenced_block_is_run_and_prose_around_it_is_ignored():
    r = run_code("python", "Here:\n```python\nprint('hi')\n```\nenjoy", ["python"])
    assert r["out_output"] == "hi" and r["out_ran"] and r["out_program"] == "print('hi')\n"


def test_bare_code_is_run_but_prose_is_not():
    assert run_code("py", "print(1 + 1)", ["python"])["out_output"] == "2"
    r = run_code("python", "Sure! Here is a friendly program.", ["python"])
    assert r["out_output"] == "(not run: the reply has no code block and is not valid python)" and not r["out_ran"]


def test_a_failing_fenced_block_is_reported_not_raised():
    r = run_code("python", "```python\nraise SystemExit(3)\n```", ["python"])
    assert r["out_output"].startswith("(it failed with exit code 3)") and not r["out_ran"]


def test_a_language_that_is_not_allowed_is_returned_not_run():
    r = run_code("javascript", "console.log(1)", ["python"])
    assert r["out_output"].startswith("(not run: only python are run, not javascript)")
    assert run_code("go", "package main", ["python", "javascript"])["out_output"].startswith("(not run:")


def test_timeout_and_empty_text():
    assert run_code("python", "```python\nwhile True: pass\n```", ["python"], timeout=0.5)["out_output"].startswith("(stopped:")
    assert run_code("python", "   ", ["python"])["out_output"] == "(not run: no code to run)"


def test_the_environment_is_empty_and_the_folder_is_a_throwaway():
    r = run_code("python", "```python\nimport os\nprint(os.environ.get('HOME'), os.getcwd() != '/')\n```", ["python"])
    assert r["out_output"] == "None True"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_javascript_runs():
    assert run_code("js", "```js\nconsole.log(6 * 7)\n```", ["javascript"])["out_output"] == "42"


def test_checks():
    ok = {"id": "r", "type": "RUN_CODE", "ports": ["trigger", "complete", "in_language", "in_text"], "config": {"languages": ["python"]}}
    assert check_run_code(ok)[0] == []
    bad = {**ok, "config": {"languages": ["go"], "timeout": -1, "x": 1}}
    assert len(check_run_code(bad)[0]) == 3
    assert code_of("```\nx\n```") == ("x\n", True)


def test_run_code_needs_a_guard_and_a_delta_cannot_set_its_languages():
    from graphlang.grafr.solve_backend import CODE_KEYS
    from graphlang.grafr.topology import _risky
    assert _risky({"type": "RUN_CODE", "config": {}}) and "languages" in CODE_KEYS
