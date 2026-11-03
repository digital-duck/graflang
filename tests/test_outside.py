"""QUERY, EMIT and OBSERVE: the nodes that touch the world outside the graph (grafr/outside.py)."""
import json
import smtplib
import urllib.request
from pathlib import Path

import pytest
import yaml

from graphlang.grafr import outside
from graphlang.grafr.outside import OutsideError, check_outside
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.solve_backend import CODE_KEYS
from graphlang.grafr.topology import check

POLICY = 'permit (principal, action, resource);\n'


def node(typ, nid="n", ports=None, **cfg):
    return {"id": nid, "type": typ, "ports": ports or ["trigger", "complete"], "config": cfg}


def build(tmp_path: Path, emit_cfg=None, query_cfg=None, observe=True, notes="# notes\nhello\n"):
    """entry -> GUARD(allow) -> QUERY -> OBSERVE -> EMIT -> OUTPUT, in a folder of its own."""
    (tmp_path / "policies").mkdir(exist_ok=True)
    (tmp_path / "policies" / "p.cedar").write_text(POLICY)
    if notes is not None:
        (tmp_path / "notes.md").write_text(notes)
    nodes = [
        {"id": "wf_entry", "type": "INPUT", "ports": ["entry", "out_text"]},
        {"id": "g", "type": "GUARD", "ports": ["trigger", "allow", "deny", "in_text"],
         "config": {"policy_ref": "policies.p", "principal": 'User::"u"', "action": 'Action::"go"', "resource": 'Thing::"t"', "context_mapping": {}}},
        {"id": "read", "type": "QUERY", "ports": ["trigger", "complete", "out_notes"], "config": query_cfg or {"file": "notes.md"}},
        {"id": "send", "type": "EMIT", "ports": ["trigger", "complete", "in_content", "out_receipt"],
         "config": emit_cfg or {"channel": "file", "file": "out/result.txt"}},
        {"id": "done", "type": "OUTPUT", "ports": ["trigger", "exit", "in_result"]},
    ]
    edges = [
        {"source": "wf_entry.entry", "target": "g.trigger", "type": "triggers"},
        {"source": "wf_entry.out_text", "target": "g.in_text", "type": "binds"},
        {"source": "g.allow", "target": "read.trigger", "type": "triggers"},
        {"source": "send.complete", "target": "done.trigger", "type": "triggers"},
        {"source": "send.out_receipt", "target": "done.in_result", "type": "binds"},
    ]
    if observe:
        nodes.insert(3, {"id": "watch", "type": "OBSERVE", "ports": ["trigger", "complete", "in_notes", "out_notes"], "config": {"label": "what was read"}})
        edges += [{"source": "read.complete", "target": "watch.trigger", "type": "triggers"},
                  {"source": "read.out_notes", "target": "watch.in_notes", "type": "binds"},
                  {"source": "watch.complete", "target": "send.trigger", "type": "triggers"},
                  {"source": "watch.out_notes", "target": "send.in_content", "type": "binds"}]
    else:
        edges += [{"source": "read.complete", "target": "send.trigger", "type": "triggers"},
                  {"source": "read.out_notes", "target": "send.in_content", "type": "binds"}]
    graph = {"version": "1.0-graph",
             "workflow": {"name": "outside", "inputs": [{"name": "text", "type": "TEXT", "default": "x"}], "outputs": [{"name": "result", "type": "JSON"}]},
             "resources": {"policies": {"p": "./policies/p.cedar"}}, "nodes": nodes, "edges": edges}
    path = tmp_path / "outside.graph.yaml"
    path.write_text(yaml.safe_dump(graph, sort_keys=False))
    return path


def run(path, **kw):
    rt = GraphLangRuntime(load_graph(path), adapter="mock", verbose=False, **kw)
    return rt.execute({"text": "x"}), rt


# ---- a whole run -----------------------------------------------------------------------------------------------
def test_query_observe_emit_run_end_to_end(tmp_path):
    path = build(tmp_path)
    errors, _ = check(load_graph(path))
    assert errors == []
    out, _ = run(path, effects=True)
    assert out["result"]["channel"] == "file" and out["result"]["mode"] == "write"
    assert (tmp_path / "out" / "result.txt").read_text() == "# notes\nhello\n"


def test_a_dry_run_does_not_write(tmp_path):
    path = build(tmp_path)
    out, _ = run(path)                                          # the mock adapter: nothing leaves the process
    assert out["result"] == {"channel": "file", "dry_run": True, "chars": len("# notes\nhello\n")}
    assert not (tmp_path / "out").exists()


def test_observe_writes_to_the_run_folder_and_passes_values_on(tmp_path):
    from graphlang.grafr.output import RunOutput
    path = build(tmp_path)
    run_output = RunOutput(tmp_path / "runs", "outside", "mock")
    out, _ = run(path, effects=True, node_output=run_output)
    lines = [json.loads(x) for x in (run_output.dir / "observations.jsonl").read_text().splitlines()]
    assert lines[0]["node"] == "watch" and lines[0]["label"] == "what was read" and lines[0]["values"]["notes"] == "# notes\nhello\n"
    assert (tmp_path / "out" / "result.txt").exists()           # OBSERVE handed the value on to EMIT


def test_observe_never_stops_a_run(tmp_path, monkeypatch):
    path = build(tmp_path)

    class Broken:
        def observe(self, *a, **k):
            raise OSError("disk full")

        def save_node(self, *a, **k):
            return []
    out, _ = run(path, effects=True, node_output=Broken())
    assert out["result"]["channel"] == "file"


# ---- QUERY -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("fmt, text, want", [("text", "a\nb", "a\nb"), ("json", '{"a": 1}', {"a": 1}), ("yaml", "a: [1, 2]", {"a": [1, 2]}), ("lines", "a\nb\n", ["a", "b"])])
def test_query_reads_each_format(tmp_path, fmt, text, want):
    (tmp_path / "f.txt").write_text(text)
    n = node("QUERY", ports=["trigger", "complete", "out_v"], file="f.txt", format=fmt)
    assert outside.run_query(n, {}, tmp_path) == {"out_v": want}


def test_query_refuses_a_path_outside_the_graph_folder(tmp_path):
    (tmp_path / "inside").mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("no")
    n = node("QUERY", ports=["trigger", "complete", "out_v"], file="../secret.txt")
    with pytest.raises(OutsideError, match="outside the graph's folder"):
        outside.run_query(n, {}, tmp_path / "inside")
    n = node("QUERY", ports=["trigger", "complete", "out_v"], file=str(secret))
    with pytest.raises(OutsideError):
        outside.run_query(n, {}, tmp_path / "inside")
    outside.run_query({**n, "config": {**n["config"], "allow_dirs": [str(tmp_path)]}}, {}, tmp_path / "inside")      # allowed when listed


def test_query_refuses_a_link_out_of_the_folder(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    (tmp_path / "secret.txt").write_text("no")
    (inside / "link.txt").symlink_to(tmp_path / "secret.txt")
    with pytest.raises(OutsideError):
        outside.run_query(node("QUERY", ports=["trigger", "complete", "out_v"], file="link.txt"), {}, inside)


def test_query_missing_file_fails_unless_there_is_a_default(tmp_path):
    n = node("QUERY", ports=["trigger", "complete", "out_v"], file="none.txt")
    with pytest.raises(OutsideError, match="no such file"):
        outside.run_query(n, {}, tmp_path)
    n["config"]["default"] = "empty"
    assert outside.run_query(n, {}, tmp_path) == {"out_v": "empty"}


def test_query_size_limit_and_bad_json(tmp_path):
    (tmp_path / "big.txt").write_text("x" * 50)
    with pytest.raises(OutsideError, match="max_bytes"):
        outside.run_query(node("QUERY", ports=["trigger", "complete", "out_v"], file="big.txt", max_bytes=10), {}, tmp_path)
    (tmp_path / "bad.json").write_text("{nope")
    with pytest.raises(OutsideError, match="not valid json"):
        outside.run_query(node("QUERY", ports=["trigger", "complete", "out_v"], file="bad.json", format="json"), {}, tmp_path)


# ---- EMIT ------------------------------------------------------------------------------------------------------
def test_emit_file_append_and_confinement(tmp_path):
    n = node("EMIT", ports=["trigger", "complete", "in_content", "out_receipt"], channel="file", file="log/a.txt", mode="append")
    outside.run_emit(n, {"in_content": "one"}, tmp_path)
    outside.run_emit(n, {"in_content": "two"}, tmp_path)
    assert (tmp_path / "log" / "a.txt").read_text() == "one\ntwo\n"
    n["config"]["file"] = "../escape.txt"
    with pytest.raises(OutsideError):
        outside.run_emit(n, {"in_content": "x"}, tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()


def test_emit_stdout(tmp_path, capsys):
    n = node("EMIT", ports=["trigger", "complete", "in_content", "out_receipt"], channel="stdout")
    assert outside.run_emit(n, {"in_content": {"a": 1}}, tmp_path)["out_receipt"]["channel"] == "stdout"
    assert '"a": 1' in capsys.readouterr().out


def test_emit_webhook_posts_json_and_checks_the_host(tmp_path, monkeypatch):
    seen = {}

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def add_handler(self, h):
            pass

        def open(self, request, timeout=None):
            seen["url"], seen["body"], seen["timeout"] = request.full_url, json.loads(request.data), timeout
            return Response()
    monkeypatch.setattr(urllib.request, "build_opener", lambda: Opener())
    n = node("EMIT", ports=["trigger", "complete", "in_content", "out_receipt"], channel="webhook", url="https://hooks.example.com/x", allow_hosts=["hooks.example.com"])
    assert outside.run_emit(n, {"in_content": "hello", "in_subject": "S"}, tmp_path)["out_receipt"] == {"channel": "webhook", "status": 204}
    assert seen["body"] == {"subject": "S", "content": "hello"}
    n["config"]["allow_hosts"] = ["other.example.com"]
    with pytest.raises(OutsideError, match="allow_hosts"):
        outside.run_emit(n, {"in_content": "hello"}, tmp_path)


def test_emit_email_uses_fixed_recipients_and_env_credentials(tmp_path, monkeypatch):
    sent = {}

    class SMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"], sent["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, msg):
            sent["msg"] = msg
    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    monkeypatch.setenv("GRAF_SMTP_USER", "u")
    monkeypatch.setenv("GRAF_SMTP_PASSWORD", "p")
    n = node("EMIT", ports=["trigger", "complete", "in_content", "out_receipt"], channel="email", recipients=["me@example.com"], sender="graf@example.com",
             smtp_host="smtp.example.com", subject="Done")
    out = outside.run_emit(n, {"in_content": "body text"}, tmp_path)
    assert out["out_receipt"] == {"channel": "email", "recipients": ["me@example.com"]}
    assert sent["host"] == "smtp.example.com" and sent["port"] == 587 and sent["tls"] and sent["login"] == ("u", "p")
    assert sent["msg"]["To"] == "me@example.com" and sent["msg"]["Subject"] == "Done" and "body text" in sent["msg"].get_content()


def test_emit_a_dry_run_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("a dry run must not connect"))
    n = node("EMIT", ports=["trigger", "complete", "in_content", "out_receipt"], channel="email", recipients=["me@example.com"], sender="a@b.c", smtp_host="h")
    assert outside.run_emit(n, {"in_content": "x"}, tmp_path, effects=False)["out_receipt"]["dry_run"] is True


# ---- graf validate ---------------------------------------------------------------------------------------------
def test_validate_checks_each_node(tmp_path):
    def errs(n):
        return check_outside(n, tmp_path)[0]
    assert any("needs `file`" in m for m in errs(node("QUERY", ports=["trigger", "complete", "out_v"])))
    assert any("outside" in m for m in errs(node("QUERY", ports=["trigger", "complete", "out_v"], file="../x")))
    assert any("format" in m for m in errs(node("QUERY", ports=["trigger", "complete", "out_v"], file="a", format="xml")))
    assert any("out_*" in m for m in errs(node("QUERY", file="a")))
    emit_ports = ["trigger", "complete", "in_content"]
    assert any("channel" in m for m in errs(node("EMIT", ports=emit_ports)))
    assert any("in_content" in m for m in errs(node("EMIT", channel="stdout")))
    assert any("allow_hosts" in m for m in errs(node("EMIT", ports=emit_ports, channel="webhook", url="https://a.example/x")))
    assert any("recipients" in m for m in errs(node("EMIT", ports=emit_ports, channel="email", sender="a@b.c", smtp_host="h")))
    assert errs(node("EMIT", ports=emit_ports, channel="file", file="out/a.txt")) == []
    assert check_outside(node("OBSERVE"), tmp_path)[1]          # no in_* port: nothing to observe


def test_validate_requires_a_guard_before_query_and_emit(tmp_path):
    path = build(tmp_path)
    graph = load_graph(path)
    for e in graph["edges"]:                                    # route straight from the entry, around the GUARD
        if e["target"] == "read.trigger":
            e["source"] = "wf_entry.entry"
    errors, _ = check(graph)
    assert any("without passing a GUARD" in m for m in errors)


def test_a_mutate_delta_can_never_set_where_a_node_reads_or_sends():
    for key in ("file", "channel", "recipients", "sender", "smtp_host", "smtp_port", "allow_dirs", "url", "allow_hosts"):
        assert key in CODE_KEYS


def test_validate_warns_when_a_node_that_reaches_outside_is_retried(tmp_path):
    path = build(tmp_path, emit_cfg={"channel": "file", "file": "out/a.txt", "phases": {"exec": {"retry": {"max": 2}}}})
    _, warnings = check(load_graph(path))
    assert any("idempotent" in m and "'send'" in m for m in warnings)
    path = build(tmp_path)
    assert not any("idempotent" in m for m in check(load_graph(path))[1])


def test_on_node_streams_each_finished_node(tmp_path):
    path = build(tmp_path)
    seen = []
    run(path, effects=False, on_node=seen.append)
    assert [e["node"] for e in seen][:2] == ["g", "read"] and "send" in [e["node"] for e in seen]
    read = next(e for e in seen if e["node"] == "read")
    assert read["type"] == "QUERY" and read["outputs"] == {"out_notes": "# notes\nhello\n"} and read["ms"] >= 0


def test_a_broken_listener_does_not_stop_the_run(tmp_path):
    path = build(tmp_path)

    def bad(event):
        raise RuntimeError("listener bug")
    out, _ = run(path, effects=False, on_node=bad)
    assert out["result"]["dry_run"] is True


def test_graf_run_stream_prints_nodes_as_they_finish(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    path = build(tmp_path)
    result = CliRunner().invoke(main, ["run", str(path), "--stream", "--no-log", "--no-output"])
    assert result.exit_code == 0, result.output
    assert "QUERY read" in result.output and "out_notes:" in result.output and "EMIT send" in result.output


def test_query_tail_keeps_the_last_lines(tmp_path):
    (tmp_path / "chat.md").write_text("1\n2\n3\n4\n")
    n = node("QUERY", ports=["trigger", "complete", "out_v"], file="chat.md", tail=2)
    assert outside.run_query(n, {}, tmp_path) == {"out_v": "3\n4\n"}
    n["config"]["format"] = "lines"
    assert outside.run_query(n, {}, tmp_path) == {"out_v": ["3", "4"]}
    assert any("tail" in m for m in check_outside(node("QUERY", ports=["trigger", "complete", "out_v"], file="x", tail=0), tmp_path)[0])
