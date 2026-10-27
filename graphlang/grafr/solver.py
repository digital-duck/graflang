"""Subprocess solver backend for SOLVE: run a black-box program, read its stdout through a declared parser, type-check the value.

Contract (see the design note, solver backends):
- stdin: the node's inputs as one JSON object, written by graflang.
- stdout: whatever the solver prints. It is read by a declared parser (built in, or a user-written Python function) and
  must yield a value of the declared output type. Nothing is guessed: no parser match, or a value of the wrong type, is a
  failure, and the raw stdout and stderr are kept in the error.
- exit code: non-zero, a timeout, or a memory-limit kill is a failure.

The runtime reaches it through solve_backend.py (`SOLVE` with `backend: subprocess`); this module itself knows nothing about graphs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import resource
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

TIMEOUT = 60
MEMORY_MB = 2048
OUT_TYPES = ("BOOL", "INTEGER", "REAL", "TEXT", "JSON")


class SolverError(RuntimeError):
    """A solver run failed. `stdout` and `stderr` are the raw outputs, kept for the run log."""

    def __init__(self, message: str, stdout: str = "", stderr: str = "", returncode: Optional[int] = None):
        super().__init__(message)
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


@dataclass
class SolverResult:
    value: Any
    stdout: str
    stderr: str
    returncode: int
    seconds: float
    parser: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------------------- parsers
# A parser takes the raw stdout (text) and returns the value, or None when it finds nothing. It never guesses.

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_last_json(stdout: str) -> Any:
    """The last JSON object or array in stdout (a fenced block counts). None if there is none."""
    candidates = [m.group(1).strip() for m in _FENCE.finditer(stdout)]
    candidates += [line.strip() for line in stdout.splitlines() if line.strip()[:1] in "{["]
    for text in reversed(candidates):
        try:
            return json.loads(text)
        except ValueError:
            continue
    return None


def parse_first_line(stdout: str, tokens: Optional[List[str]] = None) -> Any:
    """The first non-empty line, stripped. With `tokens`, the line must start with one of them (case-insensitive) and
    the matched token is returned; otherwise None."""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    first = lines[0]
    if tokens is None:
        return first
    for token in tokens:
        if first.lower().startswith(token.lower()):
            return token
    return None


def parse_regex(stdout: str, pattern: str) -> Any:
    """The named group `value` of the first match of `pattern` (a single unnamed group is also accepted). None if no match."""
    m = re.search(pattern, stdout, re.M)
    if not m:
        return None
    if "value" in m.groupdict():
        return m.group("value")
    return m.group(1) if m.groups() else m.group(0)


BUILTIN_PARSERS = ("last_json", "first_line", "regex")


def load_custom_parser(spec: str, base_dir: Path) -> Callable[[str], Any]:
    """`spec` is `file.py:function`, relative to `base_dir` (the graph's folder). The file is loaded as a module."""
    if ":" not in spec:
        raise ValueError(f"custom parser {spec!r} must be written as file.py:function")
    file_name, func_name = spec.rsplit(":", 1)
    path = (base_dir / file_name).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"custom parser file not found: {path}")
    module_name = f"_graflang_parser_{abs(hash(str(path)))}"
    loader_spec = importlib.util.spec_from_file_location(module_name, path)
    if loader_spec is None or loader_spec.loader is None:
        raise ImportError(f"cannot load {path.name} as a Python module")
    module = importlib.util.module_from_spec(loader_spec)
    loader_spec.loader.exec_module(module)
    func = getattr(module, func_name, None)
    if not callable(func):
        raise AttributeError(f"{path.name} does not define a function {func_name!r}")
    return func


def read_output(parse: Any, stdout: str, base_dir: Path) -> tuple[Any, str]:
    """Apply the declared parser. Returns (value, description of the parser used). `parse` is one of:
    "last_json" | "first_line" | {"first_line": [tokens]} | {"regex": pattern} | {"tool": "file.py:function"}."""
    if parse == "last_json":
        return parse_last_json(stdout), "last_json"
    if parse == "first_line":
        return parse_first_line(stdout), "first_line"
    if isinstance(parse, dict):
        if "first_line" in parse:
            tokens = parse["first_line"]
            return parse_first_line(stdout, list(tokens)), f"first_line{list(tokens)}"
        if "regex" in parse:
            return parse_regex(stdout, parse["regex"]), f"regex {parse['regex']!r}"
        if "tool" in parse:
            func = load_custom_parser(parse["tool"], base_dir)
            return func(stdout), f"tool {parse['tool']}"
    raise ValueError(f"unknown parser declaration {parse!r} (built-in: {', '.join(BUILTIN_PARSERS)}, or {{tool: file.py:function}})")


# ---------------------------------------------------------------------------------------------------------- type check

def check_type(value: Any, out_type: str) -> Any:
    """The value must have the declared type. Returns the value (a bool stays a bool). Raises ValueError otherwise."""
    if out_type not in OUT_TYPES:
        raise ValueError(f"unknown output type {out_type!r} (one of {', '.join(OUT_TYPES)})")
    if value is None:
        raise ValueError("the parser found no value")
    checks = {
        "BOOL": lambda v: isinstance(v, bool),
        "INTEGER": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "REAL": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "TEXT": lambda v: isinstance(v, str),
        "JSON": lambda v: isinstance(v, (dict, list, str, int, float, bool)) or v is None,
    }
    if not checks[out_type](value):
        raise ValueError(f"expected {out_type}, got {type(value).__name__} {str(value)[:80]!r}")
    return value


# ---------------------------------------------------------------------------------------------------------- the run

def _text(captured) -> str:
    """Output captured before a timeout may arrive as bytes; keep it as text for the log."""
    if captured is None:
        return ""
    return captured.decode("utf-8", errors="replace") if isinstance(captured, bytes) else captured


def _limits(memory_mb: int):
    limit = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_solver(command: List[str], inputs: Dict[str, Any], *, parse: Any, out_type: str, base_dir: Path,
               timeout: float = TIMEOUT, memory_mb: int = MEMORY_MB, cwd: Optional[Path] = None,
               env: Optional[Dict[str, str]] = None) -> SolverResult:
    """Run `command` with `inputs` as JSON on stdin, read stdout through `parse`, type-check against `out_type`.

    Raises SolverError (with the raw stdout and stderr) on a non-zero exit, a timeout, an unparseable output, or a value
    of the wrong type. A missing command is a SolverError too, so the caller reports it like any other failure.

    The solver sees only PATH and what is in `env`: nothing else of the caller's environment (no keys, no HOME) leaks to it."""
    payload = json.dumps(inputs, default=str)
    start = time.perf_counter()
    try:
        done = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=timeout,
                              cwd=str(cwd) if cwd else None, env={"PATH": os.environ.get("PATH", ""), "PYTHONUTF8": "1", **(env or {})},
                              preexec_fn=lambda: _limits(memory_mb))
    except subprocess.TimeoutExpired as e:
        raise SolverError(f"solver timed out after {timeout}s", stdout=_text(e.stdout), stderr=_text(e.stderr)) from None
    except FileNotFoundError:
        raise SolverError(f"solver command not found: {command[0]!r}") from None
    seconds = time.perf_counter() - start
    if done.returncode != 0:
        tail = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
        raise SolverError(f"solver exited {done.returncode}: {tail[:200]}", done.stdout, done.stderr, done.returncode)
    try:
        value, used = read_output(parse, done.stdout, base_dir)
        value = check_type(value, out_type)
    except Exception as e:                          # any parser or type failure, including a user parser's own errors
        raise SolverError(f"output not accepted: {e}", done.stdout, done.stderr, done.returncode) from None
    return SolverResult(value=value, stdout=done.stdout, stderr=done.stderr, returncode=done.returncode,
                        seconds=seconds, parser=used)
