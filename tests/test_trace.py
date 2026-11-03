"""graf trace: a run's JSONL log as spans (grafr/trace.py)."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.trace import TraceError, read_events, spans_of, to_otlp, to_tree

EVENTS = [
    {"ts": "2026-11-03T10:00:00.000+00:00", "event": "run.start", "workflow": "demo", "adapter": "claude_cli", "model": "m"},
    {"ts": "2026-11-03T10:00:01.000+00:00", "event": "llm.call", "node": "draft", "adapter": "claude_cli", "model": "m", "prompt_chars": 100, "response_chars": 400, "ms": 900},
    {"ts": "2026-11-03T10:00:01.010+00:00", "event": "node.done", "node": "draft", "type": "GENERATE", "n": 1, "depth": 0, "route": None, "ms": 1010},
    {"ts": "2026-11-03T10:00:01.020+00:00", "event": "node.done", "node": "gate", "type": "EVALUATE", "n": 1, "depth": 0, "route": "pass", "ms": 10},
    {"ts": "2026-11-03T10:00:02.000+00:00", "event": "run.end", "workflow": "demo", "steps": 3, "ms": 2000},
]


def write(tmp_path, events=EVENTS):
    path = tmp_path / "run.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def test_spans_follow_the_log(tmp_path):
    trace = spans_of(read_events(write(tmp_path)))
    run, draft, gate = trace["spans"]
    assert run["name"] == "run demo" and run["status"] == "ok" and run["end"] - run["start"] == 2_000_000_000
    assert draft["name"] == "GENERATE draft" and draft["end"] - draft["start"] == 1010 * 1_000_000 and draft["parent"] == run["id"]
    assert draft["attributes"]["llm.model"] == "m" and draft["attributes"]["llm.response_chars"] == 400
    assert gate["attributes"]["route"] == "pass" and "llm.model" not in gate["attributes"]


def test_otlp_has_the_shape_a_collector_reads(tmp_path):
    otlp = to_otlp(spans_of(read_events(write(tmp_path))))
    spans = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 3 and len(spans[0]["traceId"]) == 32 and len(spans[0]["spanId"]) == 16
    assert "parentSpanId" not in spans[0] and spans[1]["parentSpanId"] == spans[0]["spanId"]
    assert int(spans[1]["endTimeUnixNano"]) > int(spans[1]["startTimeUnixNano"])
    assert {"key": "service.name", "value": {"stringValue": "graflang"}} in otlp["resourceSpans"][0]["resource"]["attributes"]


def test_a_failed_run_marks_the_error(tmp_path):
    events = EVENTS[:3] + [{"ts": "2026-11-03T10:00:01.500+00:00", "event": "run.fail", "workflow": "demo", "error": "RunLimitExceeded: stopped"}]
    trace = spans_of(read_events(write(tmp_path, events)))
    assert trace["spans"][0]["status"] == "error" and "RunLimitExceeded" in trace["spans"][0]["attributes"]["error"]
    assert "[error]" in to_tree(trace)


def test_tree_shows_each_node_on_the_time_axis(tmp_path):
    text = to_tree(spans_of(read_events(write(tmp_path))))
    assert text.splitlines()[0].startswith("run demo") and "GENERATE draft" in text and "-> pass" in text and "#" in text


def test_a_text_log_is_refused(tmp_path):
    bad = tmp_path / "run.log"
    bad.write_text("08:13:02  INFO  run.start workflow=demo\n")
    with pytest.raises(TraceError, match="not JSON"):
        read_events(bad)
    with pytest.raises(TraceError, match="no run.start"):
        spans_of([{"ts": "2026-11-03T10:00:00+00:00", "event": "node.done"}])


def test_graf_trace_prints_writes_and_picks_the_newest_log(tmp_path, monkeypatch):
    path = write(tmp_path)
    result = CliRunner().invoke(main, ["trace", str(path)])
    assert result.exit_code == 0 and "GENERATE draft" in result.output
    out = tmp_path / "t.json"
    result = CliRunner().invoke(main, ["trace", str(path), "--format", "otlp", "-o", str(out)])
    assert result.exit_code == 0 and json.loads(out.read_text())["resourceSpans"]
    monkeypatch.setenv("DD_LOG_DIR", str(tmp_path))
    assert "run demo" in CliRunner().invoke(main, ["trace"]).output
    monkeypatch.setenv("DD_LOG_DIR", str(tmp_path / "empty"))
    assert CliRunner().invoke(main, ["trace"]).exit_code != 0


# ---- graf watch -------------------------------------------------------------------------------------------------
def test_watch_runs_on_a_schedule_and_passes_the_options_on(monkeypatch):
    import subprocess
    import time
    calls, sleeps = [], []

    class Done:
        def __init__(self, code):
            self.returncode, self.stdout, self.stderr = code, "Output: {}\n", ""
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: calls.append(cmd) or Done(0))
    monkeypatch.setattr(time, "sleep", sleeps.append)
    result = CliRunner().invoke(main, ["watch", "g.graph.yaml", "--every", "5", "--times", "3", "--param", "x=1", "--llm", "claude_cli:m"])
    assert result.exit_code == 0 and result.output.count(": ok") == 3
    assert len(calls) == 3 and calls[0][-6:] == ["run", "g.graph.yaml", "--param", "x=1", "--llm", "claude_cli:m"][-6:]
    assert len(sleeps) == 2 and all(0 <= s <= 5 for s in sleeps)               # no sleep after the last run


def test_watch_stops_after_failures_in_a_row(monkeypatch):
    import subprocess
    import time

    class Done:
        returncode, stdout, stderr = 1, "", "boom\n"
    runs = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: runs.append(1) or Done())
    monkeypatch.setattr(time, "sleep", lambda s: None)
    result = CliRunner().invoke(main, ["watch", "g.graph.yaml", "--times", "0", "--max-failures", "2"])
    assert result.exit_code != 0 and "2 failed runs in a row" in result.output and len(runs) == 2
