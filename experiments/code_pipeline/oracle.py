"""The independent oracle: run the model's code against the task's hidden unit tests in a separate process.

The tests are never shown to any arm. A task passes only when the program exits 0 within the time limit; no code, a
syntax error, a missing function, a wrong answer and a timeout are all failures. The imports at the top of the task's prompt
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

TIMEOUT = 10
MEMORY = 2 * 1024 ** 3


@dataclass
class Verdict:
    passed: bool
    reason: str          # "pass", "no_code", "timeout", or the last line of the error


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


def program(task: dict, code: str) -> str:
    return f"{header_imports(task['prompt'])}\n{code}\n\n{task['test']}\n\ncheck({task['entry_point']})\n"


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))


def check(task: dict, code: str, timeout: float = TIMEOUT) -> Verdict:
    if not code or not code.strip():
        return Verdict(False, "no_code")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(program(task, code))
        try:
            run = subprocess.run([sys.executable, "-I", path], cwd=tmp, env={"PATH": os.environ.get("PATH", "")},
                                 capture_output=True, text=True, timeout=timeout, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            return Verdict(False, "timeout")
    if run.returncode == 0:
        return Verdict(True, "pass")
    tail = (run.stderr.strip().splitlines() or [f"exit {run.returncode}"])[-1]
    return Verdict(False, tail[:200])
