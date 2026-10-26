"""Persistent Python kernel backend for SOLVE (`config.backend: kernel`), over jupyter_client.

A kernel runs the node's `code` (trusted: it is written in the graph file, never taken from a model). Inputs reach the code
as data: they travel as one JSON string literal and are bound to variables, so a bound value that looks like Python is
still only a string. The node's `result` expression is evaluated after the code and its JSON value is read back from a
marker line on stdout; anything else the code prints is ignored.

Scope: `run` shares one kernel across all kernel nodes of a run (started on the first firing, shut down when the run ends,
including on Ctrl-C); `node` starts a fresh kernel for each firing. A timeout restarts the kernel, so its variables are gone.

Needs `pip install graflang[kernel]` (jupyter_client and ipykernel). Nothing here is imported until a kernel node fires.
"""
from __future__ import annotations

import atexit
import json
import keyword
import os
import queue
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

STARTUP_TIMEOUT = 60
MARKER = "__GRAFLANG_RESULT__"


class KernelError(RuntimeError):
    """The code raised, timed out, or did not produce a JSON result."""


def build_cell(inputs: Dict[str, Any], code: str, result: str) -> str:
    """The text one firing executes: bind the inputs, run `code`, print `result` as JSON after the marker.

    The inputs are serialised to JSON and embedded with `repr`, which yields a string literal that cannot end early, so no
    input value can change the code that runs."""
    for name in inputs:
        if not name.isidentifier() or keyword.iskeyword(name):
            raise KernelError(f"input {name!r} is not a usable Python variable name")
    payload = json.dumps(inputs, default=str)
    return (f"import json as __json\nglobals().update(__json.loads({payload!r}))\n"
            f"{code.rstrip()}\n"
            f"print({MARKER!r} + __json.dumps({result}))\n")


def read_result(stdout: str) -> Any:
    """The JSON value on the last marker line. Raises KernelError if there is none."""
    for line in reversed(stdout.splitlines()):
        if line.startswith(MARKER):
            try:
                return json.loads(line[len(MARKER):])
            except ValueError as e:
                raise KernelError(f"the result is not valid JSON: {e}") from None
    raise KernelError("the code produced no result")


class KernelSession:
    """One running kernel."""

    def __init__(self, seed: Optional[int] = None):
        try:
            from jupyter_client.manager import KernelManager
        except ImportError:
            raise KernelError("the kernel backend needs jupyter_client and ipykernel: pip install 'graflang[kernel]'") from None
        try:
            # Unix sockets are protected by file permissions; the default TCP ports on localhost would let any local user
            # connect and run code as this user.
            self.km = KernelManager(kernel_name="python3", transport="ipc" if os.name == "posix" else "tcp")
            self.km.start_kernel()
            self.kc = self.km.client()
            self.kc.start_channels()
            self.kc.wait_for_ready(timeout=STARTUP_TIMEOUT)
        except Exception as e:
            self.close()
            raise KernelError(f"could not start a Python kernel: {e}") from None
        if seed is not None:
            self._run(f"import random as __random; __random.seed({int(seed)})\n"
                      f"try:\n    import numpy as __numpy; __numpy.random.seed({int(seed)})\nexcept ImportError:\n    pass\n",
                      STARTUP_TIMEOUT)

    def execute(self, inputs: Dict[str, Any], code: str, result: str, timeout: float) -> Any:
        return read_result(self._run(build_cell(inputs, code, result), timeout))

    def _run(self, cell: str, timeout: float) -> str:
        """Execute `cell` and return its stdout. Raises KernelError on an exception or after `timeout` seconds."""
        msg_id = self.kc.execute(cell, store_history=False)
        deadline = time.monotonic() + timeout
        stdout, failure = [], None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._restart()
                raise KernelError(f"timed out after {timeout}s (the kernel was restarted)")
            try:
                msg = self.kc.get_iopub_msg(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if msg["parent_header"].get("msg_id") != msg_id:
                continue
            kind, content = msg["msg_type"], msg["content"]
            if kind == "stream" and content.get("name") == "stdout":
                stdout.append(content["text"])
            elif kind == "error":
                failure = f"{content['ename']}: {content['evalue']}"
            elif kind == "status" and content.get("execution_state") == "idle":
                break
        if failure:
            raise KernelError(failure)
        return "".join(stdout)

    def _restart(self) -> None:
        try:
            self.km.restart_kernel(now=True)
            self.kc.wait_for_ready(timeout=STARTUP_TIMEOUT)
        except Exception:
            pass

    def close(self) -> None:
        for stop in (lambda: self.kc.stop_channels(), lambda: self.km.shutdown_kernel(now=True)):
            try:
                stop()
            except Exception:                       # a half-started session has no client yet; nothing to stop
                pass


class KernelPool:
    """The kernels of one run. The root runtime owns it and closes it when the run ends."""

    def __init__(self):
        self._shared: Optional[KernelSession] = None
        self._registered = False

    @contextmanager
    def session(self, scope: str = "run", seed: Optional[int] = None) -> Iterator[KernelSession]:
        if scope == "node":
            fresh = KernelSession(seed)
            try:
                yield fresh
            finally:
                fresh.close()
            return
        if self._shared is None:
            self._shared = KernelSession(seed)      # the seed applies when the run's kernel starts
            if not self._registered:
                atexit.register(self.close)         # a safety net if the runtime never reaches its `finally`
                self._registered = True
        yield self._shared

    def close(self) -> None:
        if self._shared is not None:
            self._shared.close()
            self._shared = None
