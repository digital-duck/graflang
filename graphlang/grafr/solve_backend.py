"""`SOLVE` with a `backend`: run deterministic code (a Python kernel) or a black-box program (a subprocess).

Both backends keep one contract (see docs/DEV/design-solver-kernel.md): each `in_<name>` port is a named JSON value, the one
`out_*` port (other than `out_error`) receives a value of the declared `out_type`, and an exception, a timeout or a bad
output fails the node. With `on_error: route` and an `error` port the failure goes to that port instead of ending the run,
and the message is written to `out_error` if the node has that port.

This module also holds what is known about a backend node's config: the static checks `graf validate` runs on it, and the
keys a MUTATE delta must never set (`CODE_KEYS`).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import time
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..logging_config import ERROR, WARNING, get_logger, log_event
from .kernel import KernelError, KernelPool
from .solver import BUILTIN_PARSERS, MEMORY_MB, OUT_TYPES, TIMEOUT, SolverError, check_type, run_solver

_log = get_logger("grafr.solve")

BACKENDS = ("kernel", "subprocess")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SCOPES = ("run", "node")
# Config keys that decide what runs. They come from the graph file, never from a model: a MUTATE delta that adds or changes
# one is refused before any policy is consulted (see `code_keys_in`).
CODE_KEYS = frozenset({"backend", "code", "result", "command", "parse", "env_passthrough"})   # env can change what runs (NODE_OPTIONS, PYTHONPATH)


class SolveError(RuntimeError):
    """A backend SOLVE failed (the message names the node)."""


def code_keys_in(value: Any) -> List[str]:
    """The CODE_KEYS used as a key anywhere inside `value` (a dict or list of any depth), sorted. A LOOP's `subgraph` is a
    nested graph, so a node added inside it would be found here too."""
    found: set = set()

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            found.update(k for k in v if k in CODE_KEYS)
            for item in v.values():
                walk(item)
        elif isinstance(v, list):
            for item in v:
                walk(item)

    walk(value)
    return sorted(found)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------------------------------------- running

def run_backend(node_data: Dict, in_data: Dict[str, Any], resolver, kernels: KernelPool) -> Dict:
    """Run one firing of a backend SOLVE and return its outputs (and `_route: error` when a failure is routed)."""
    cfg, node_id, ports = node_data["config"], node_data["id"], node_data["ports"]
    backend = cfg["backend"]
    inputs = {name[3:]: value for name, value in in_data.items()}
    out_type = cfg.get("out_type", "JSON")
    timeout = cfg.get("timeout", TIMEOUT)
    started = time.perf_counter()
    fields: Dict[str, Any] = {"node": node_id, "backend": backend, "inputs": sorted(inputs)}
    try:
        if backend == "kernel":
            fields["code_sha"] = _digest(cfg["code"] + "\n" + cfg["result"])
            with kernels.session(cfg.get("scope", "run"), cfg.get("seed")) as kernel:
                value = check_type(kernel.execute(inputs, cfg["code"], cfg["result"], timeout), out_type)
        elif backend == "subprocess":
            names = cfg.get("env_passthrough", [])
            unset = [n for n in names if n not in os.environ]
            if unset:                                          # declared means needed: fail, never run without it
                raise ValueError(f"env_passthrough names {unset}, which are not set in the environment this run started in")
            fields.update(command=cfg["command"], input_sha=_digest(json.dumps(inputs, default=str, sort_keys=True)),
                          env=list(names))                       # names only, never values
            res = run_solver(cfg["command"], inputs, parse=cfg.get("parse", "last_json"), out_type=out_type,
                             base_dir=resolver.base_dir, timeout=timeout, memory_mb=cfg.get("memory_mb", MEMORY_MB),
                             cwd=resolver.base_dir, env={n: os.environ[n] for n in names})
            value, fields["output_sha"], fields["parser"] = res.value, _digest(res.stdout), res.parser
        else:
            raise ValueError(f"unknown backend {backend!r} (one of {', '.join(BACKENDS)})")
    except (SolverError, KernelError, ValueError) as e:
        message = f"{type(e).__name__}: {e}"
        routed = cfg.get("on_error") == "route" and "error" in ports
        log_event(_log, f"solve.{backend}.exec", level=WARNING if routed else ERROR, outcome="routed" if routed else "failed",
                  error=message, ms=round((time.perf_counter() - started) * 1000), **fields)
        if routed:
            return {"_route": "error", **({"out_error": str(e)} if "out_error" in ports else {})}
        raise SolveError(f"SOLVE node {node_id!r}: {e}") from e
    log_event(_log, f"solve.{backend}.exec", outcome="ok", ms=round((time.perf_counter() - started) * 1000), **fields)
    out_ports = [p for p in ports if p.startswith("out_") and p != "out_error"]
    return {out_ports[0]: value}


# ---------------------------------------------------------------------------------------------------------- checking

def _names_in(source: str, mode: str) -> set:
    return {n.id for n in ast.walk(ast.parse(source, mode=mode)) if isinstance(n, ast.Name)}


def _tool_defines(path: Path, func: str) -> bool:
    """Does the parser file define `func`? Read with `ast`: validation never runs user code."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func for n in ast.walk(tree))


def check_solve(node: Dict, base_dir: Path) -> Tuple[List[str], List[str]]:
    """Static checks for one SOLVE node: (errors, warnings). Errors are what graflang itself cannot run; warnings are the
    parts that come from the user and may be fine on the machine that runs the graph (a missing command, a requirement)."""
    cfg, ports = node.get("config", {}), node["ports"]
    errors: List[str] = []
    warnings: List[str] = []
    backend = cfg.get("backend")
    if backend is None:
        if not any(k in cfg for k in ("expression", "procedure_ref")):
            errors.append("computes nothing: give it a backend, an expression or a procedure_ref")
        return errors, warnings
    if backend not in BACKENDS:
        return [f"unknown backend {backend!r} (one of {', '.join(BACKENDS)})"], warnings
    for k in ("expression", "procedure_ref"):
        if k in cfg:
            errors.append(f"a backend SOLVE cannot also have {k}")
    if cfg.get("out_type", "JSON") not in OUT_TYPES:
        errors.append(f"unknown out_type {cfg['out_type']!r} (one of {', '.join(OUT_TYPES)})")
    for key in ("timeout", "memory_mb"):
        if key in cfg and not (isinstance(cfg[key], (int, float)) and not isinstance(cfg[key], bool) and cfg[key] > 0):
            errors.append(f"{key} must be a positive number")
    if cfg.get("on_error", "fail") not in ("fail", "route"):
        errors.append("on_error must be 'fail' or 'route'")
    elif cfg.get("on_error") == "route" and "error" not in ports:
        errors.append("on_error: route needs an 'error' port")
    results = [p for p in ports if p.startswith("out_") and p != "out_error"]
    if len(results) != 1:
        errors.append(f"a backend SOLVE needs exactly one result port out_* (besides out_error), found {len(results)}")
    in_names = [p[3:] for p in ports if p.startswith("in_")]

    if backend == "kernel":
        if "env_passthrough" in cfg:
            errors.append("env_passthrough applies to backend: subprocess; a kernel inherits the runtime's environment")
        used = None
        if not isinstance(cfg.get("code"), str) or not isinstance(cfg.get("result"), str):
            errors.append("a kernel SOLVE needs `code` and `result` (text)")
        else:
            try:
                used = _names_in(cfg["code"], "exec") | _names_in(cfg["result"], "eval")
            except SyntaxError as e:
                errors.append(f"code or result has a syntax error: {e.msg} (line {e.lineno})")
        if cfg.get("scope", "run") not in SCOPES:
            errors.append(f"scope must be one of {', '.join(SCOPES)}")
        for name in in_names:
            if not name.isidentifier() or name.startswith("__"):
                errors.append(f"port in_{name} is not usable as a Python variable")
            elif used is not None and name not in used:
                warnings.append(f"input in_{name} is never used by the code or the result")
        if find_spec("jupyter_client") is None or find_spec("ipykernel") is None:
            warnings.append("the kernel backend needs `pip install 'graflang[kernel]'` (jupyter_client, ipykernel)")
    else:
        command = cfg.get("command")
        if not (isinstance(command, list) and command and all(isinstance(c, str) for c in command)):
            errors.append("a subprocess SOLVE needs `command`: a list of strings, e.g. [python, solvers/check.py]")
        elif not ((base_dir / command[0]).exists() if "/" in command[0] else shutil.which(command[0])):
            warnings.append(f"command {command[0]!r} was not found on this machine")
        errors += _check_parse(cfg.get("parse", "last_json"), base_dir, warnings)
        names = cfg.get("env_passthrough", [])
        if not (isinstance(names, list) and all(isinstance(n, str) and ENV_NAME.fullmatch(n) for n in names)):
            errors.append("env_passthrough must be a list of environment variable names, e.g. [HOME, NODE_PATH]")
        else:
            warnings += [f"env_passthrough: {n} is not set here; the run fails unless it is set where it runs"
                         for n in names if n not in os.environ]
        for item in cfg.get("requirements", []):
            if not isinstance(item, str):
                errors.append("requirements must be a list of names")
            elif shutil.which(item) is None and find_spec(item.split(".")[0]) is None:
                warnings.append(f"requirement {item!r} is not installed (neither a command on PATH nor a Python module)")
    return errors, warnings


def _check_parse(parse: Any, base_dir: Path, warnings: List[str]) -> List[str]:
    if isinstance(parse, str):
        return [] if parse in ("last_json", "first_line") else [
            f"unknown parser {parse!r} (built in: {', '.join(BUILTIN_PARSERS)})"]
    if not isinstance(parse, dict) or len(parse) != 1:
        return [f"parse must be a built-in name or a one-key mapping (first_line, regex or tool), got {parse!r}"]
    (kind, arg), = parse.items()
    if kind == "first_line":
        return [] if isinstance(arg, list) and arg and all(isinstance(t, str) for t in arg) else [
            "parse.first_line must be a list of tokens"]
    if kind == "regex":
        try:
            re.compile(arg)
        except (re.error, TypeError) as e:
            return [f"parse.regex does not compile: {e}"]
        return []
    if kind == "tool":
        if not isinstance(arg, str) or ":" not in arg:
            return ["parse.tool must be written as file.py:function"]
        file_name, func = arg.rsplit(":", 1)
        path = base_dir / file_name
        try:
            if not path.is_file():
                warnings.append(f"parser file {file_name!r} was not found next to the graph")
            elif not _tool_defines(path, func):
                warnings.append(f"parser file {file_name!r} does not define a function {func!r}")
        except SyntaxError as e:
            warnings.append(f"parser file {file_name!r} has a syntax error: {e.msg}")
        return []
    return [f"unknown parser kind {kind!r} (first_line, regex or tool)"]
