"""Node lifecycle: `pre -> exec -> post`, declared under `config.phases` (design E1).

    phases:
      pre:  {require: [in_topic], defaults: {in_style: concise}}
      exec: {timeout_s: 60, retry: {max: 3, wait_s: 2, on: [transient, invalid_output]}, fallback: {route: error} | {value: ""}}
      post: {out_schema: {type: object, required: [summary]}, route: {retry: "@out_summary == ''"}}

* `pre` checks that the required in_* values are present (not None) and fills the defaults.
* `exec` is the node's executor, the only retried step. Failures are `transient` (an adapter or OS error, a
  timeout), `invalid_output` (post rejected the result) or `permanent` (bad configuration: never retried).
  Retries are `max` extra attempts, waiting `wait_s` between them; `on` says which classes are retried
  (default: transient only). A GENERATE retried for invalid_output sees the validation error under
  `_validation_error` and asks again.
* `timeout_s` gives each attempt that many seconds; a slower one counts as a `transient` failure. The attempt runs on
  a worker thread that cannot be killed, so a timed-out call may keep running in the background until it ends.
* `fallback` applies when exec still fails: `{route: <port>}` leaves by that control port (the node must have it;
  the message goes on `out_error` if it has that port) or `{value: X}` puts X on the first out_* port.
  A fallback value goes through `post` like any result.
* `post` checks the first out_* value against `out_schema` (JSON Schema). A string is parsed as JSON first
  (a ```json fence is allowed) and the parsed value replaces it, so the next node sees data, not text.
  `route` maps a control port to a condition over the node's in_* and out_* values (as `@out_text`); the first true
  one in order sends the token there instead of the default port. A node that already chose a `_route` keeps it.

A node without `phases` runs exactly as before.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from jsonschema import Draft202012Validator

from .expr import ExpressionError, evaluate_condition, variables
from ..logging_config import WARNING, get_logger, log_event

_log = get_logger("grafr.lifecycle")

PHASE_KEYS = {"pre": {"require", "defaults"}, "exec": {"timeout_s", "retry", "fallback"}, "post": {"out_schema", "route"}}
RETRY_KEYS = {"max", "wait_s", "on"}
ERROR_CLASSES = {"transient", "invalid_output"}
FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", re.DOTALL)


class InvalidOutput(ValueError):
    """A node's result broke its `out_schema`."""


def _classify(exc: Exception) -> str:
    """Config and evaluation errors are permanent; I/O, timeout and adapter errors may pass on a second try."""
    if isinstance(exc, InvalidOutput):
        return "invalid_output"
    retryable = getattr(exc, "retryable", None)               # RUN errors say so themselves
    if retryable is not None:
        return "transient" if retryable else "permanent"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "permanent"
    return "transient"


def _first_out(node_data: Dict) -> Optional[str]:
    return next((p for p in node_data["ports"] if p.startswith("out_")), None)


def _pre(node_data: Dict, in_data: Dict, spec: Dict) -> Dict:
    data = dict(in_data)
    for port, value in spec.get("defaults", {}).items():
        if data.get(port) is None:
            data[port] = value
    missing = [p for p in spec.get("require", []) if data.get(p) is None]
    if missing:
        raise ValueError(f"node {node_data['id']!r}: required input(s) {missing} have no value")
    return data


def _parse(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    fenced = FENCE.match(text)
    try:
        return json.loads(fenced.group(1) if fenced else text)
    except json.JSONDecodeError as e:
        raise InvalidOutput(f"the output is not valid JSON ({e.msg} at char {e.pos})") from None


def _post(node_data: Dict, result: Dict, spec: Dict, in_data: Dict) -> Dict:
    schema = spec.get("out_schema")
    port = _first_out(node_data)
    if schema is not None and port is not None and "_route" not in result:
        value = _parse(result.get(port))
        error = next(iter(Draft202012Validator(schema).iter_errors(value)), None)
        if error is not None:
            where = "/".join(str(p) for p in error.absolute_path) or "(root)"
            raise InvalidOutput(f"{where}: {error.message}")
        result = {**result, port: value}
    if spec.get("route") and "_route" not in result:
        scope = {**{k: v for k, v in in_data.items() if not k.startswith("_")},
                 **{k: v for k, v in result.items() if not k.startswith("_")}}
        for target, condition in spec["route"].items():
            if evaluate_condition(condition, scope):
                return {**result, "_route": target}
    return result


def _call_with_timeout(execute: Callable[[Dict], Dict], data: Dict, seconds: Optional[float]) -> Dict:
    if not seconds:
        return execute(data)
    box: Dict[str, Any] = {}

    def work():
        try:
            box["result"] = execute(data)
        except BaseException as e:                              # re-raised in the caller's thread
            box["error"] = e

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"exec took longer than {seconds}s")
    if "error" in box:
        raise box["error"]
    return box["result"]


def _fallback(node_data: Dict, spec: Dict, error: Exception) -> Dict:
    if "route" in spec:
        out = {"_route": spec["route"]}
        if "out_error" in node_data["ports"]:
            out["out_error"] = f"{type(error).__name__}: {error}"
        return out
    port = _first_out(node_data)
    return {port: spec["value"]} if port else {}


def run_phases(node_data: Dict, in_data: Dict, execute: Callable[[Dict], Dict],
               sleep: Optional[Callable[[float], None]] = None) -> Dict:
    """Run `execute(in_data)` through the node's phases. `execute` is the node's executor."""
    phases = node_data.get("config", {}).get("phases")
    if not phases:
        return execute(in_data)
    nid = node_data["id"]
    data = _pre(node_data, in_data, phases.get("pre", {}))
    ex = phases.get("exec", {})
    retry = ex.get("retry", {})
    retried_on = set(retry.get("on", ["transient"]))
    attempts = 1 + int(retry.get("max", 0))
    post = phases.get("post", {})
    feedback: Optional[str] = None
    error: Exception = RuntimeError("no attempt ran")
    for attempt in range(1, attempts + 1):
        try:
            attempt_data = {**data, "_validation_error": feedback} if feedback else data
            return _post(node_data, _call_with_timeout(execute, attempt_data, ex.get("timeout_s")) or {}, post, data)
        except Exception as e:                                  # classified below; permanent ones re-raise or fall back
            error = e
            kind = _classify(e)
            log_event(_log, "node.attempt_failed", level=WARNING, node=nid, attempt=attempt, of=attempts,
                      error_class=kind, error=f"{type(e).__name__}: {e}")
            if kind not in retried_on or attempt == attempts:
                break
            feedback = str(e) if kind == "invalid_output" else None
            if retry.get("wait_s"):
                (sleep or time.sleep)(float(retry["wait_s"]))
    fallback = ex.get("fallback")
    if fallback is None:
        raise error
    log_event(_log, "node.fallback", level=WARNING, node=nid, **{k: str(v) for k, v in fallback.items()})
    return _post(node_data, _fallback(node_data, fallback, error), post, data)


def check_phases(node_data: Dict) -> List[str]:
    """`graf validate` messages for one node's `config.phases`."""
    phases = node_data.get("config", {}).get("phases")
    if phases is None:
        return []
    if not isinstance(phases, dict):
        return ["phases must be a mapping with pre, exec and post"]
    errors: List[str] = []
    ports = node_data["ports"]
    for name, spec in phases.items():
        if name not in PHASE_KEYS:
            errors.append(f"phases has unknown phase {name!r} (use pre, exec, post)")
        elif not isinstance(spec, dict):
            errors.append(f"phases.{name} must be a mapping")
        else:
            errors += [f"phases.{name} has unknown key {k!r} (use {sorted(PHASE_KEYS[name])})"
                       for k in spec if k not in PHASE_KEYS[name]]
    section = lambda k: phases[k] if isinstance(phases.get(k), dict) else {}
    pre, ex, post = section("pre"), section("exec"), section("post")
    for p in [*pre.get("require", []), *pre.get("defaults", {})]:
        if p not in ports or not p.startswith("in_"):
            errors.append(f"phases.pre names {p!r}, which is not an in_* port of the node")
    if "timeout_s" in ex and (not isinstance(ex["timeout_s"], (int, float)) or ex["timeout_s"] <= 0):
        errors.append("phases.exec.timeout_s must be a number > 0")
    routes = post.get("route", {})
    if not isinstance(routes, dict):
        errors.append("phases.post.route must map a control port to a condition")
    else:
        known = {p for p in ports if p.startswith(("in_", "out_"))}
        for target, condition in routes.items():
            if target not in ports or target.startswith(("in_", "out_")) or target == "trigger":
                errors.append(f"phases.post.route sends to {target!r}, which is not a control port of the node")
            try:
                unknown = variables(condition) - known
            except (ExpressionError, TypeError) as e:
                errors.append(f"phases.post.route.{target}: {e}")
                continue
            if unknown:
                errors.append(f"phases.post.route.{target}: uses {sorted('@' + u for u in unknown)}, not an in_* or out_* port")
    retry = ex.get("retry", {})
    if not isinstance(retry, dict):
        errors.append("phases.exec.retry must be a mapping")
    else:
        errors += [f"phases.exec.retry has unknown key {k!r} (use {sorted(RETRY_KEYS)})" for k in retry if k not in RETRY_KEYS]
        if not isinstance(retry.get("max", 0), int) or retry.get("max", 0) < 0:
            errors.append("phases.exec.retry.max must be a whole number >= 0")
        if not isinstance(retry.get("wait_s", 0), (int, float)) or retry.get("wait_s", 0) < 0:
            errors.append("phases.exec.retry.wait_s must be a number >= 0")
        bad = [c for c in retry.get("on", []) if c not in ERROR_CLASSES]
        if bad:
            errors.append(f"phases.exec.retry.on has {bad}; permanent errors are never retried (use {sorted(ERROR_CLASSES)})")
    fb = ex.get("fallback")
    if fb is not None:
        if not isinstance(fb, dict) or len(fb) != 1 or next(iter(fb)) not in ("route", "value"):
            errors.append("phases.exec.fallback needs exactly one of route or value")
        elif "route" in fb and fb["route"] not in ports:
            errors.append(f"phases.exec.fallback routes to {fb['route']!r}, which is not a port of the node")
        elif "value" in fb and _first_out(node_data) is None:
            errors.append("phases.exec.fallback.value needs an out_* port to put it on")
    if "out_schema" in post:
        if _first_out(node_data) is None:
            errors.append("phases.post.out_schema needs an out_* port to check")
        try:
            Draft202012Validator.check_schema(post["out_schema"])
        except Exception as e:
            errors.append(f"phases.post.out_schema is not a JSON Schema: {getattr(e, 'message', e)}")
    return errors
