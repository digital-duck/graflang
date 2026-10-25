"""The independent oracle: run the model's code against the task's hidden unit tests in a separate process.

The tests are never shown to any arm. A task passes only when every assertion holds and the program exits 0 within the time
limit (its `__main__` block, if any, does not run). No code, a syntax error, a missing function, a wrong answer and a timeout
are all failures; the verdict also records how many of the assertions held, so a near miss can be told from a wrong program. The imports at the top of the task's prompt
(for example `from typing import List`) are prepended, because the spec shows them and a model may not repeat them.

This executes untrusted model output. It runs in a temporary directory with `python -I`, a CPU-time and a memory limit, and
no inherited environment, but it is not a security sandbox: it can still read files and use the network. Run the experiment
in a container or a throwaway account if that matters.
"""
from __future__ import annotations

import ast
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# The candidate runs as a module named "candidate", not as `__main__`: code a model adds under `if __name__ == "__main__":`
# (its own tests, a demo) must not run or decide the verdict. HumanEval's reference harness gets the same effect by exec.
RUNNER = "import runpy, sys; runpy.run_path(sys.argv[1], run_name='candidate')"

TIMEOUT = 10
MEMORY = 2 * 1024 ** 3


@dataclass
class Verdict:
    passed: bool
    reason: str          # "pass", "no_code", "timeout", or the last line of the error
    assert_passed: int = 0   # how many of the task's assertions held (a near miss has most of them)
    assert_total: int = 0    # how many assertions the test ran (0 when the program never got that far)


def header_imports(prompt: str) -> str:
    """The import lines of the prompt (top-level `import` / `from ... import` statements before the first def)."""
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return ""
    lines = prompt.splitlines()
    out = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    return "\n".join(out)


# Each `assert` in the hidden tests becomes a call to _tally, which runs it and counts it instead of stopping at the first
# failure. The footer prints the count (for the scorer to read) and then fails the program if any assertion failed, so the
# pass/fail verdict is the same as running the tests as written.
TALLY_HEADER = """
_TALLY = [0, 0]
def _tally(test):
    _TALLY[1] += 1
    try:
        ok = bool(test())
    except Exception:
        ok = False
    if ok:
        _TALLY[0] += 1
"""
TALLY_FOOTER = """
try:
    check({entry})
finally:
    print("__TALLY__", _TALLY[0], _TALLY[1], flush=True)
if _TALLY[0] < _TALLY[1]:
    raise AssertionError(f"{{_TALLY[1] - _TALLY[0]}} of {{_TALLY[1]}} assertions failed")
"""


class _Asserts(ast.NodeTransformer):
    def visit_Assert(self, node: ast.Assert):
        call = ast.Call(func=ast.Name(id="_tally", ctx=ast.Load()),
                        args=[ast.Lambda(args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                                         body=node.test)],
                        keywords=[])
        return ast.copy_location(ast.Expr(value=call), node)


def tallied_test(test: str) -> str:
    tree = _Asserts().visit(ast.parse(test))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def program(task: dict, code: str) -> str:
    return (f"{header_imports(task['prompt'])}\n{code}\n\n{TALLY_HEADER}\n{tallied_test(task['test'])}\n"
            f"{TALLY_FOOTER.format(entry=task['entry_point'])}")


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))


def _counts(stdout: str) -> tuple[int, int]:
    for line in reversed(stdout.splitlines()):
        if line.startswith("__TALLY__"):
            _, passed, total = line.split()
            return int(passed), int(total)
    return 0, 0


def check(task: dict, code: str, timeout: float = TIMEOUT) -> Verdict:
    if not code or not code.strip():
        return Verdict(False, "no_code")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(program(task, code))
        try:
            run = subprocess.run([sys.executable, "-I", "-c", RUNNER, path], cwd=tmp, env={"PATH": os.environ.get("PATH", "")},
                                 capture_output=True, text=True, timeout=timeout, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            return Verdict(False, "timeout")
    passed_n, total_n = _counts(run.stdout)
    if run.returncode == 0:
        return Verdict(True, "pass", passed_n, total_n)
    tail = (run.stderr.strip().splitlines() or [f"exit {run.returncode}"])[-1]
    return Verdict(False, tail[:200], passed_n, total_n)
