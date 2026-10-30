"""`RUN`: deterministic work done by an *executor* (design E4). One contract for all of them: each `in_<name>` port is a named
JSON value in, the one `out_*` port (besides `out_error`) gets a value of the declared `out_type` out, and a failure, a timeout
or a bad answer fails the node, or goes to the `error` port with `on_error: route`.

    executor: subprocess   any program that reads JSON on stdin (same keys as SOLVE backend: subprocess)
    executor: python       code in a persistent Python kernel (same keys as SOLVE backend: kernel)
    executor: http         POST the inputs as JSON to `url` and read JSON back; `allow_hosts` is required

The http protocol: the request body is `{"inputs": {name: value}}`; the answer is `{"result": value}` or the value itself, or
`{"error": {"code": "...", "message": "...", "retryable": true}}`. A 5xx, 429 or `retryable: true` is retryable (a `phases.exec.retry`
with `on: [transient]` will try again); other failures are permanent.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from ..logging_config import ERROR, WARNING, get_logger, log_event
from .kernel import KernelPool
from .solve_backend import SolveError, check_solve, run_backend
from .solver import OUT_TYPES, TIMEOUT, check_type

_log = get_logger("grafr.run")

EXECUTORS = ("subprocess", "python", "http")
BACKEND_OF = {"subprocess": "subprocess", "python": "kernel"}
METHODS = ("POST", "PUT", "PATCH")
MAX_BODY = 5_000_000


class RunError(RuntimeError):
    """A RUN failed. `retryable` tells the lifecycle whether another attempt may help."""

    def __init__(self, message: str, retryable: bool = False, code: str = ""):
        super().__init__(message)
        self.retryable, self.code = retryable, code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):               # a redirect could leave the allowlist
        return None


def _as_solve(node: Dict) -> Dict:
    cfg = {k: v for k, v in node.get("config", {}).items() if k != "executor"}
    cfg["backend"] = BACKEND_OF[node["config"]["executor"]]
    return {**node, "type": "SOLVE", "config": cfg}


def _result_port(node: Dict) -> str:
    return next(p for p in node["ports"] if p.startswith("out_") and p != "out_error")


def run_run(node: Dict, in_data: Dict[str, Any], resolver, kernels: KernelPool) -> Dict:
    cfg = node.get("config", {})
    executor = cfg.get("executor")
    if executor in BACKEND_OF:
        try:
            return run_backend(_as_solve(node), in_data, resolver, kernels)
        except SolveError as e:
            raise RunError(str(e).replace("SOLVE node", "RUN node", 1)) from e
    if executor != "http":
        raise ValueError(f"RUN node {node['id']!r}: unknown executor {executor!r} (one of {', '.join(EXECUTORS)})")
    return _run_http(node, in_data)


def _run_http(node: Dict, in_data: Dict[str, Any]) -> Dict:
    cfg, nid, ports = node["config"], node["id"], node["ports"]
    url, started = cfg["url"], time.perf_counter()
    host = urlparse(url).hostname
    if host not in cfg.get("allow_hosts", []):
        raise ValueError(f"RUN node {nid!r}: host {host!r} is not in allow_hosts {cfg.get('allow_hosts', [])}")
    body = json.dumps({"inputs": {k[3:]: v for k, v in in_data.items() if k.startswith("in_")}}, default=str).encode()
    request = urllib.request.Request(url, data=body, method=cfg.get("method", "POST"),
                                     headers={"Content-Type": "application/json", "Accept": "application/json", **cfg.get("headers", {})})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        try:
            with opener.open(request, timeout=cfg.get("timeout", TIMEOUT)) as response:
                raw = response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as e:
            raw = e.read(MAX_BODY + 1)
            error = _protocol_error(raw)
            raise RunError(error[0] if error else f"HTTP {e.code} from {host}",
                           retryable=error[1] if error else (e.code >= 500 or e.code == 429), code=error[2] if error else str(e.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RunError(f"{host} unreachable: {getattr(e, 'reason', e)}", retryable=True, code="unreachable") from None
        if len(raw) > MAX_BODY:
            raise RunError(f"answer from {host} is over {MAX_BODY} bytes")
        error = _protocol_error(raw)
        if error:
            raise RunError(error[0], retryable=error[1], code=error[2])
        try:
            answer = json.loads(raw)
        except json.JSONDecodeError:
            raise RunError(f"answer from {host} is not JSON") from None
        value = answer["result"] if isinstance(answer, dict) and set(answer) == {"result"} else answer
        try:
            value = check_type(value, cfg.get("out_type", "JSON"))
        except ValueError as e:
            raise RunError(f"answer from {host}: {e}") from None
    except RunError as e:
        routed = cfg.get("on_error") == "route" and "error" in ports
        log_event(_log, "run.http", level=WARNING if routed else ERROR, node=nid, host=host, outcome="routed" if routed else "failed",
                  error=str(e), retryable=e.retryable, ms=round((time.perf_counter() - started) * 1000))
        if routed:
            return {"_route": "error", **({"out_error": str(e)} if "out_error" in ports else {})}
        raise
    log_event(_log, "run.http", node=nid, host=host, outcome="ok", ms=round((time.perf_counter() - started) * 1000))
    return {_result_port(node): value}


def _protocol_error(raw: bytes) -> Tuple[str, bool, str] | None:
    try:
        answer = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    err = answer.get("error") if isinstance(answer, dict) else None
    if isinstance(err, dict):
        return str(err.get("message", "error")), bool(err.get("retryable", False)), str(err.get("code", ""))
    return None


def check_run(node: Dict, base_dir: Path) -> Tuple[List[str], List[str]]:
    """`graf validate` for one RUN node: (errors, warnings)."""
    cfg, ports = node.get("config", {}), node["ports"]
    executor = cfg.get("executor")
    if executor in BACKEND_OF:
        return check_solve(_as_solve(node), base_dir)
    if executor != "http":
        return [f"executor must be one of {', '.join(EXECUTORS)}, not {executor!r}"], []
    errors: List[str] = []
    url = cfg.get("url")
    if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname:
        errors.append("an http RUN needs `url` (http or https)")
    hosts = cfg.get("allow_hosts")
    if not (isinstance(hosts, list) and hosts and all(isinstance(h, str) for h in hosts)):
        errors.append("an http RUN needs `allow_hosts`: the host names it may call, e.g. [api.example.com]")
    elif isinstance(url, str) and urlparse(url).hostname not in hosts:
        errors.append(f"url host {urlparse(url).hostname!r} is not in allow_hosts")
    if cfg.get("method", "POST") not in METHODS:
        errors.append(f"method must be one of {', '.join(METHODS)}")
    if cfg.get("out_type", "JSON") not in OUT_TYPES:
        errors.append(f"unknown out_type {cfg['out_type']!r} (one of {', '.join(OUT_TYPES)})")
    if "timeout" in cfg and not (isinstance(cfg["timeout"], (int, float)) and cfg["timeout"] > 0):
        errors.append("timeout must be a positive number")
    if not isinstance(cfg.get("headers", {}), dict):
        errors.append("headers must be a mapping")
    if cfg.get("on_error", "fail") not in ("fail", "route"):
        errors.append("on_error must be 'fail' or 'route'")
    elif cfg.get("on_error") == "route" and "error" not in ports:
        errors.append("on_error: route needs an 'error' port")
    if len([p for p in ports if p.startswith("out_") and p != "out_error"]) != 1:
        errors.append("a RUN needs exactly one result port out_* (besides out_error)")
    return errors, []
