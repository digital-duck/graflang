"""RUN (design E4): deterministic work by an executor (subprocess, python kernel, http), one contract for all."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.util import find_spec
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime
from graphlang.grafr.run_node import RunError
from graphlang.grafr.topology import check

SOLVER_DIR = Path(__file__).parent.parent / "cookbook" / "solver_check"
needs_kernel = pytest.mark.skipif(find_spec("jupyter_client") is None or find_spec("ipykernel") is None, reason="needs graflang[kernel]")


def graph(run_cfg, ports=("trigger", "complete", "in_numbers", "out_total"), source_dir=SOLVER_DIR, edges=()):
    return {"version": "1.0-graph", "_source_dir": str(source_dir), "resources": {},
            "workflow": {"name": "t", "inputs": [{"name": "numbers", "type": "TEXT"}], "outputs": [{"name": "total", "type": "JSON"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_numbers"]},
                      {"id": "r", "type": "RUN", "config": run_cfg, "ports": list(ports)},
                      {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_total"]}],
            "edges": [{"source": "s.entry", "target": "r.trigger", "type": "triggers"},
                      {"source": "s.out_numbers", "target": "r.in_numbers", "type": "binds"},
                      {"source": "r.out_total", "target": "o.in_total", "type": "binds"},
                      {"source": "r.complete", "target": "o.trigger", "type": "triggers"}, *edges]}


def test_subprocess_executor_is_the_solve_backend_under_the_run_name():
    cfg = {"executor": "subprocess", "command": ["python3", "-I", "solvers/sum_numbers.py"], "parse": {"tool": "solvers/parsers.py:total"},
           "out_type": "INTEGER"}
    g = graph(cfg)
    assert check(g)[0] == []
    assert GraphLangRuntime(g, verbose=False).execute({"numbers": "1,2,3"}) == {"total": 6}


@needs_kernel
def test_python_executor_runs_in_a_kernel():
    g = graph({"executor": "python", "code": "total = sum(int(x) for x in numbers.split(','))", "result": "total", "out_type": "INTEGER"})
    assert check(g)[0] == []
    assert GraphLangRuntime(g, verbose=False).execute({"numbers": "4,5"}) == {"total": 9}


class Handler(BaseHTTPRequestHandler):
    calls = 0
    mode = "ok"

    def do_POST(self):
        type(self).calls += 1
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        mode = type(self).mode
        if mode == "flaky" and type(self).calls == 1:
            return self._send(503, {"error": {"code": "busy", "message": "try later", "retryable": True}})
        if mode == "bad":
            return self._send(400, {"error": {"code": "invalid", "message": "numbers are wrong", "retryable": False}})
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://other.example/")
            return self.end_headers()
        if mode == "text":
            return self._send(200, "not a number")
        self._send(200, {"result": sum(int(x) for x in body["inputs"]["numbers"].split(","))})

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    Handler.calls, Handler.mode = 0, "ok"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/sum"
    srv.shutdown()


def http_cfg(url, **extra):
    return {"executor": "http", "url": url, "allow_hosts": ["127.0.0.1"], "out_type": "INTEGER", "timeout": 5, **extra}


def test_http_executor_posts_inputs_and_reads_the_result(server):
    g = graph(http_cfg(server))
    assert check(g)[0] == []
    assert GraphLangRuntime(g, verbose=False).execute({"numbers": "1,2,3,4"}) == {"total": 10}


def test_a_retryable_answer_is_retried_by_the_lifecycle(server):
    Handler.mode = "flaky"
    g = graph(http_cfg(server, phases={"exec": {"retry": {"max": 2, "on": ["transient"]}}}))
    assert GraphLangRuntime(g, verbose=False).execute({"numbers": "2,2"}) == {"total": 4} and Handler.calls == 2


def test_a_permanent_error_is_not_retried_and_can_be_routed(server):
    Handler.mode = "bad"
    g = graph(http_cfg(server, phases={"exec": {"retry": {"max": 3, "on": ["transient"]}}}))
    with pytest.raises(RunError, match="numbers are wrong") as info:
        GraphLangRuntime(g, verbose=False).execute({"numbers": "x"})
    assert Handler.calls == 1 and info.value.retryable is False and info.value.code == "invalid"
    Handler.calls = 0
    routed = graph(http_cfg(server, on_error="route"), ports=("trigger", "complete", "error", "in_numbers", "out_total", "out_error"),
                   edges=[{"source": "r.error", "target": "o.trigger", "type": "triggers"}])
    rt = GraphLangRuntime(routed, verbose=False)
    rt.execute({"numbers": "x"})
    assert ("r", "error") in rt.emitted and rt.values[("r", "out_error")] == "numbers are wrong"


def test_wrong_type_and_redirects_fail(server):
    Handler.mode = "text"
    with pytest.raises(RunError, match="expected INTEGER"):
        GraphLangRuntime(graph(http_cfg(server)), verbose=False).execute({"numbers": "1"})
    Handler.mode = "redirect"
    with pytest.raises(RunError):
        GraphLangRuntime(graph(http_cfg(server)), verbose=False).execute({"numbers": "1"})


def test_a_host_outside_the_allowlist_is_refused_before_any_request(server):
    g = graph(http_cfg(server, allow_hosts=["api.example.com"]))
    assert any("not in allow_hosts" in m for m in check(g)[0])
    with pytest.raises(ValueError, match="not in allow_hosts"):
        GraphLangRuntime(g, verbose=False).execute({"numbers": "1"})
    assert Handler.calls == 0


@pytest.mark.parametrize("cfg, fragment", [
    ({"executor": "carrier-pigeon"}, "executor must be one of"),
    ({"executor": "http"}, "needs `url`"),
    ({"executor": "http", "url": "http://a.example/x"}, "needs `allow_hosts`"),
    ({"executor": "http", "url": "ftp://a.example/x", "allow_hosts": ["a.example"]}, "needs `url`"),
    ({"executor": "http", "url": "http://a.example/x", "allow_hosts": ["a.example"], "method": "GET"}, "method must be"),
])
def test_validate_reports_bad_run_config(cfg, fragment):
    assert any(fragment in m for m in check(graph(cfg))[0])


def test_a_delta_may_not_set_where_a_run_goes():
    from graphlang.grafr.solve_backend import code_keys_in
    assert code_keys_in({"config": {"executor": "http", "url": "http://x", "allow_hosts": ["x"]}}) == ["allow_hosts", "executor", "url"]
