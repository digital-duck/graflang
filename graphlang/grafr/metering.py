"""What a run cost and a way to run it again for free (design E9).

* `MeteredLLM` wraps the run's LLM: counts calls, tokens, cost and time, and stops the run when `limits.max_llm_calls` or
  `limits.max_cost_usd` is reached. Tokens and cost are what the adapter reports (dd-llm); an adapter that reports none counts 0.
* `RecordingLLM` writes every call to a cassette (JSON lines); `ReplayLLM` answers from one, so tests and CI never need a model.
  A call is found by its model, prompt and temperature; an unrecorded call fails loudly instead of inventing an answer. Only the
  LLM calls of GENERATE nodes go through here; a `procedure_ref` node runs SPL.py's own executor and is not recorded.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class LimitExceeded(RuntimeError):
    """A budget from the bindings (`limits.max_llm_calls`, `limits.max_cost_usd`) was reached."""


class CassetteError(RuntimeError):
    """A replay asked for a call that was not recorded, or the cassette is unreadable."""


def call_key(model: Optional[str], prompt: str, temperature: Any) -> str:
    return hashlib.sha256(json.dumps([model or "", prompt, temperature], ensure_ascii=False).encode()).hexdigest()[:20]


class MeteredLLM:
    def __init__(self, inner, max_calls: Optional[int] = None, max_cost_usd: Optional[float] = None):
        self.inner, self.max_calls, self.max_cost_usd = inner, max_calls, max_cost_usd
        self.calls = self.input_tokens = self.output_tokens = 0
        self.cost_usd = 0.0
        self.ms = 0
        self.cost_unreported = False                   # a call finished without a cost, so max_cost_usd cannot be enforced
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self.inner.name

    def __getattr__(self, attr):                       # adapter_name and the rest: a procedure_ref node reads them off the run's LLM
        if attr == "inner":
            raise AttributeError(attr)
        return getattr(self.inner, attr)

    @property
    def model_override(self):
        return getattr(self.inner, "model_override", None)

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        with self._lock:
            if self.max_calls is not None and self.calls >= self.max_calls:
                raise LimitExceeded(f"stopped before call {self.calls + 1}: limits.max_llm_calls is {self.max_calls}")
            if self.max_cost_usd is not None and self.cost_unreported:
                raise LimitExceeded(f"limits.max_cost_usd is {self.max_cost_usd} but adapter {self.name!r} reports no cost; "
                                    "use limits.max_llm_calls instead")
            if self.max_cost_usd is not None and self.cost_usd >= self.max_cost_usd:
                raise LimitExceeded(f"stopped at ${self.cost_usd:.4f}: limits.max_cost_usd is {self.max_cost_usd}")
            self.calls += 1
        started = time.perf_counter()
        try:
            return self.inner.generate(prompt, model=model, **opts)
        finally:
            usage = getattr(self.inner, "last_usage", lambda: None)() or {}
            with self._lock:
                self.ms += round((time.perf_counter() - started) * 1000)
                self.input_tokens += int(usage.get("input_tokens") or 0)
                self.output_tokens += int(usage.get("output_tokens") or 0)
                self.cost_usd += float(usage.get("cost_usd") or 0.0)
                if usage.get("cost_usd") is None and getattr(self.inner, "name", "") != "mock":
                    self.cost_unreported = True

    def snapshot(self) -> Dict[str, Any]:
        return {"adapter": self.name, "calls": self.calls, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 6), "ms": self.ms}


class RecordingLLM:
    """Passes calls to `inner` and appends each (key, response) to a JSON-lines cassette."""

    def __init__(self, inner, path: Path):
        self.inner, self.path = inner, Path(path)
        self.name = inner.name
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"cassette": 1, "adapter": inner.name, "model": getattr(inner, "model_override", None)}) + "\n", encoding="utf-8")

    def __getattr__(self, attr):
        if attr == "inner":
            raise AttributeError(attr)
        return getattr(self.inner, attr)

    @property
    def model_override(self):
        return getattr(self.inner, "model_override", None)

    def last_usage(self):
        return getattr(self.inner, "last_usage", lambda: None)()

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        response = self.inner.generate(prompt, model=model, **opts)
        entry = {"key": call_key(model, prompt, opts.get("temperature")), "model": model, "prompt_chars": len(prompt), "response": response}
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return response


class ReplayLLM:
    """Answers from a cassette. The same call recorded twice is answered in the order it was recorded."""

    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            lines = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as e:
            raise CassetteError(f"cannot read cassette {self.path}: {e}") from None
        if not lines or lines[0].get("cassette") != 1:
            raise CassetteError(f"{self.path} is not a graflang cassette")
        self.name = lines[0]["adapter"]                  # the recorded adapter, so models resolve the way they did then
        self.model_override = lines[0].get("model")     # the run's model then, so each call is keyed the same way
        self._answers: Dict[str, List[str]] = {}
        for entry in lines[1:]:
            self._answers.setdefault(entry["key"], []).append(entry["response"])
        self._lock = threading.Lock()

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        key = call_key(model, prompt, opts.get("temperature"))
        with self._lock:
            queue = self._answers.get(key)
            if not queue:
                raise CassetteError(f"no recording in {self.path.name} for this call (model {model!r}, prompt starts {prompt[:60]!r}); "
                                    f"record it again with --record")
            return queue.pop(0) if len(queue) > 1 else queue[0]
