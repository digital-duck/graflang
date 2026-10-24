"""LLM adapters for GENERATE nodes.

`make_llm(name, model)` returns an object with `.generate(prompt, model=None, **opts) -> str`.

* `mock`: no LLM; returns a canned string. The default, so nothing is billed unless you ask.
* anything else (`claude_cli`, `ollama`, `openrouter`, `anthropic`, ...): SPL.py's adapter of that name
  (`spl3.adapters.get_adapter`), so GraphLang reuses the providers, retries and subscription-safe
  environment handling already in SPL.py. `claude_cli` runs the Claude Code CLI with ANTHROPIC_API_KEY
  stripped, i.e. on your subscription, not the paid API.

DODA: the graph says *what* to generate; the provider and model are chosen when you run it
(`grafr run --adapter claude_cli --model claude-haiku-5-5`). A `model` written in a node is only a hint:
it is used when it is compatible with the chosen adapter and no `--model` was given, else ignored.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Optional


class LLMUnavailable(RuntimeError):
    """The requested adapter cannot be created (SPL.py missing, unknown name, ...)."""


def resolve_model(adapter: str, node_model: Optional[str], override: Optional[str]) -> Optional[str]:
    """Pick the model for one call: the run-time override, else the node's hint if it fits the adapter."""
    if override:
        return override
    if not node_model or adapter == "mock":
        return node_model or None
    if "/" in node_model and adapter != "openrouter":
        prefix, rest = node_model.split("/", 1)
        if prefix != adapter:
            return None                      # a hint for another provider, e.g. 'ollama/gemma3' under claude_cli
        node_model = rest
    try:
        from spl3.adapters import _model_compatible
        return node_model if _model_compatible(adapter, node_model) else None
    except ImportError:
        return node_model


class MockLLM:
    """Canned responses, for development without an LLM."""
    name = "mock"

    def __init__(self, model: Optional[str] = None):
        self.model_override = model

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        return f"[Mock LLM response from {model or 'mock'} for prompt: {prompt[:300]}...]"


def _run_coro(coro):
    """Run a coroutine to completion from sync code, even if an event loop is already running here."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict = {}

    def target():
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as e:           # re-raised in the caller's thread
            box["error"] = e

    t = threading.Thread(target=target)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def _import_spl_get_adapter():
    """SPL.py's adapter factory. If SPL.py is not installed, SPL_PY_PATH may point at a checkout of it."""
    try:
        from spl3.adapters import get_adapter
    except ImportError:
        import os
        import sys
        path = os.environ.get("SPL_PY_PATH")
        if not path or path in sys.path:
            raise
        sys.path.insert(0, path)
        from spl3.adapters import get_adapter
    return get_adapter


class SPLAdapterLLM:
    """Wraps one of SPL.py's async adapters behind the sync `generate` GraphLang nodes use."""

    def __init__(self, name: str, model: Optional[str] = None):
        try:
            get_adapter = _import_spl_get_adapter()
        except ImportError as e:
            raise LLMUnavailable("adapter %r needs SPL.py: `pip install -e /path/to/SPL.py` (or `pip install spl-llm`), "
                                 "or set SPL_PY_PATH to its folder; use --adapter mock without it" % name) from e
        try:
            self._adapter = get_adapter(name, **({"model": model} if model else {}))
        except ValueError as e:
            raise LLMUnavailable(str(e)) from e
        self.name = name
        self.adapter_name = name
        self.model_override = model

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        kwargs = {k: v for k, v in opts.items() if k in ("max_tokens", "temperature", "system") and v is not None}
        result = _run_coro(self._adapter.generate(prompt, model=model or "", **kwargs))
        return result.content


def make_llm(adapter: str = "mock", model: Optional[str] = None):
    """The LLM object for `--adapter` / `--model`."""
    if adapter == "mock":
        return MockLLM(model)
    return SPLAdapterLLM(adapter, model)
