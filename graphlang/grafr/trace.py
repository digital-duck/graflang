"""`graf trace`: a run's JSONL log (what `graf run` writes) read as a trace: one span per node firing under one run span.

Two forms. `tree` is a timeline in text (for the terminal). `otlp` is OpenTelemetry's OTLP/JSON (`resourceSpans`), which an
OpenTelemetry collector, Jaeger, Tempo or Langfuse's OTLP endpoint accepts; nothing here talks to a network, so the file is
sent by you (for example `curl -H 'Content-Type: application/json' --data @trace.json http://localhost:4318/v1/traces`).
The log is the only input: the runtime is not changed, and a run need not have been started with tracing in mind.

A node's span ends when its `node.done` line was written and lasts `ms`; a model call's model and sizes (the `llm.call` line
just before) are attributes of that span. Prompt and response text are never in the log at the default level, so they are not
in the trace either.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class TraceError(ValueError):
    """The log is not a GraphLang run log."""


def _nanos(ts: str) -> int:
    return int(datetime.fromisoformat(ts).timestamp() * 1_000_000_000)


def read_events(path: Path) -> List[Dict[str, Any]]:
    events = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            raise TraceError(f"{path}: line {n} is not JSON; a trace needs the .jsonl log, not the .log") from None
    return events


def spans_of(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """{workflow, status, start, end, spans}: the run span first, then one span per `node.done`, in the order they finished."""
    start = next((e for e in events if e.get("event") == "run.start"), None)
    if start is None:
        raise TraceError("no run.start in the log; is this a GraphLang run log (.jsonl)?")
    end = next((e for e in reversed(events) if e.get("event") in ("run.end", "run.fail")), None)
    trace_id = hashlib.sha256(f"{start['ts']}{start.get('workflow')}".encode()).hexdigest()[:32]
    run_span = {"id": hashlib.sha256((trace_id + "run").encode()).hexdigest()[:16], "parent": None, "name": f"run {start.get('workflow')}",
                "start": _nanos(start["ts"]), "end": _nanos((end or events[-1])["ts"]),
                "status": "error" if (end and end.get("event") == "run.fail") else "ok",
                "attributes": {"workflow": start.get("workflow"), "adapter": start.get("adapter"), "model": start.get("model")}}
    if end and end.get("event") == "run.fail":
        run_span["attributes"]["error"] = end.get("error")
    spans = [run_span]
    last_call: Dict[str, Dict[str, Any]] = {}
    for e in events:
        kind = e.get("event")
        if kind == "llm.call":
            last_call[e.get("node", "")] = e
        elif kind in ("node.done", "node.error"):
            stop = _nanos(e["ts"])
            ms = e.get("ms") or 0
            attrs: Dict[str, Any] = {"node": e.get("node"), "node.type": e.get("type"), "node.n": e.get("n"), "depth": e.get("depth")}
            if e.get("route"):
                attrs["route"] = e["route"]
            call = last_call.pop(e.get("node", ""), None)
            if call:
                attrs.update({"llm.adapter": call.get("adapter"), "llm.model": call.get("model"), "llm.prompt_chars": call.get("prompt_chars"),
                              "llm.response_chars": call.get("response_chars"), "llm.ms": call.get("ms")})
            if kind == "node.error":
                attrs["error"] = e.get("error")
            sid = hashlib.sha256(f"{trace_id}{len(spans)}{e.get('node')}".encode()).hexdigest()[:16]
            spans.append({"id": sid, "parent": run_span["id"], "name": f"{e.get('type')} {e.get('node')}", "start": stop - ms * 1_000_000, "end": stop,
                          "status": "error" if kind == "node.error" else "ok", "attributes": attrs})
    return {"trace_id": trace_id, "workflow": start.get("workflow"), "spans": spans}


def _attr(key: str, value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        v = {"boolValue": value}
    elif isinstance(value, int):
        v = {"intValue": str(value)}
    elif isinstance(value, float):
        v = {"doubleValue": value}
    else:
        v = {"stringValue": str(value)}
    return {"key": key, "value": v}


def to_otlp(trace: Dict[str, Any]) -> Dict[str, Any]:
    spans = []
    for s in trace["spans"]:
        item = {"traceId": trace["trace_id"], "spanId": s["id"], "name": s["name"], "kind": 1,
                "startTimeUnixNano": str(s["start"]), "endTimeUnixNano": str(s["end"]),
                "attributes": [_attr(k, v) for k, v in s["attributes"].items() if v is not None],
                "status": {"code": 2 if s["status"] == "error" else 1}}
        if s["parent"]:
            item["parentSpanId"] = s["parent"]
        spans.append(item)
    return {"resourceSpans": [{"resource": {"attributes": [_attr("service.name", "graflang"), _attr("workflow", trace["workflow"])]},
                               "scopeSpans": [{"scope": {"name": "graphlang.grafr"}, "spans": spans}]}]}


def to_tree(trace: Dict[str, Any], width: int = 40) -> str:
    """A timeline: each node's span as a bar on the run's time axis."""
    run, nodes = trace["spans"][0], trace["spans"][1:]
    total = max(run["end"] - run["start"], 1)
    lines = [f"{run['name']}  {total / 1e6:.0f} ms  [{run['status']}]"]
    for s in nodes:
        a = int((s["start"] - run["start"]) / total * width)
        b = max(a + 1, int((s["end"] - run["start"]) / total * width))
        bar = " " * a + ("#" if s["status"] == "ok" else "!") * (b - a)
        extra = []
        if s["attributes"].get("route"):
            extra.append(f"-> {s['attributes']['route']}")
        if s["attributes"].get("llm.model"):
            extra.append(f"{s['attributes']['llm.model']} {s['attributes'].get('llm.prompt_chars')}->{s['attributes'].get('llm.response_chars')} chars")
        if s["status"] == "error":
            extra.append(str(s["attributes"].get("error", ""))[:60])
        lines.append(f"  {s['name']:<28} {bar:<{width}} {(s['end'] - s['start']) / 1e6:>7.0f} ms  {' '.join(extra)}".rstrip())
    return "\n".join(lines)
