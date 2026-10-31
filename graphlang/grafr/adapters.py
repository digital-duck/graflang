"""LLM adapters for GENERATE nodes.

`make_llm(name, model)` returns an object with `.generate(prompt, model=None, **opts) -> str`.

* `mock`: no LLM; returns a canned string. The default, so nothing is billed unless you ask.
* anything else (`claude_cli`, `ollama`, `openrouter`, `anthropic`, `openai`, `gemini`, ...): the dd-llm
  adapter of that name (`dd_llm.get_adapter`). dd-llm is small and has no core dependencies, so GraphLang
  does not need SPL.py for plain LLM calls. `claude_cli` runs the Claude Code CLI with ANTHROPIC_API_KEY
  stripped, i.e. on your subscription, not the paid API.

(SPL.py is needed only for `procedure_ref` nodes; see procedures.py.)

DODA: the graph says *what* to generate; the provider and model are chosen when you run it
(`graf run --llm claude_cli:claude-haiku-5-5`). A node may name its own with `llm: adapter[:model]` (the same spec as `--llm`),
which wins for that node (fine-grained control, even another adapter); else the run's `--llm` (`--adapter`/`--model`, or `llm:` in a bindings
file) applies; else the adapter's default (claude_cli: claude-sonnet-5-5).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple


# Per-adapter default, used when neither the node nor the command line names a model. An adapter not listed (ollama, openrouter, ...) has none: the adapter's own default applies.
DEFAULT_MODELS = {"claude_cli": "claude-sonnet-5-5"}


def default_model(adapter: str) -> Optional[str]:
    return DEFAULT_MODELS.get(adapter)


class LLMUnavailable(RuntimeError):
    """The requested adapter cannot be created (dd-llm missing, unknown name, missing API key, ...)."""


def parse_node_llm(spec: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split a node's `llm:` (`ADAPTER[:MODEL]`, as `--llm`; `:MODEL` names only a model) into (adapter, model); either may be None."""
    if spec is None or spec == "":
        return None, None
    if not isinstance(spec, str):
        raise ValueError(f"llm must be a string like 'claude_cli:claude-haiku-5-5', got {spec!r}")
    adapter, _, model = spec.partition(":")
    return adapter.strip() or None, model.strip() or None


def resolve_call(run_adapter: str, spec: Optional[str], override: Optional[str], default: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """The (adapter, model) for one call. The node's own `llm:` wins, then the run's (`--llm`), then the adapter's default.
    A node that names only an adapter other than the run's gets that adapter's default model, not the run's `--llm` model.
    Under `mock` every node is answered by the mock, whatever it names."""
    adapter, model = parse_node_llm(spec)
    if run_adapter == "mock":
        return run_adapter, model or override
    adapter = adapter or run_adapter
    if adapter == run_adapter:
        return adapter, model or override or default
    return adapter, model or default_model(adapter)


class MockLLM:
    """Canned responses, for development without an LLM."""
    name = "mock"

    def __init__(self, model: Optional[str] = None):
        self.model_override = model

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        return f"[Mock LLM response from {model or 'mock'} for prompt: {prompt[:300]}...]"


class DDLLM:
    """A dd-llm adapter behind the `generate` GraphLang nodes use."""

    def __init__(self, name: str, model: Optional[str] = None, default: Optional[str] = None):
        try:
            import dd_llm
        except ImportError as e:
            raise LLMUnavailable("adapter %r needs dd-llm: `pip install dd-llm` (or `pip install -e /path/to/dd-llm`); "
                                 "use --adapter mock without it" % name) from e
        self._dd_llm = dd_llm
        self._adapters: Dict[str, Any] = {name: self._get_adapter(name)}     # others are made when a node names them
        self._adapters_lock = threading.Lock()
        self.name = name
        self.adapter_name = name
        self.model_override = model                  # chosen on the command line: applies to nodes that name no model of their own
        self.default_model = default                 # used when neither the node nor the command line names one
        self._local = threading.local()

    def _get_adapter(self, name: str):
        try:
            return self._dd_llm.get_adapter(name)
        except ValueError as e:                      # unknown adapter, or a required key / setting is missing
            raise LLMUnavailable(str(e)) from e

    def last_usage(self) -> Optional[dict]:
        """Tokens and cost the adapter reported for this thread's latest call, if it did."""
        return getattr(self._local, "usage", None)

    def generate(self, prompt: str, model: Optional[str] = None, adapter: Optional[str] = None, **opts: Any) -> str:
        """`adapter` is a node's own choice of another adapter than the run's."""
        kwargs = {k: v for k, v in opts.items() if k in ("max_tokens", "temperature", "system") and v is not None}
        adapter = adapter or self.name
        with self._adapters_lock:
            if adapter not in self._adapters:
                self._adapters[adapter] = self._get_adapter(adapter)
            chosen = self._adapters[adapter]
        try:
            result = chosen.call(prompt, model=model or "", **kwargs)
        except ImportError as e:                     # the provider's SDK is an optional extra of dd-llm
            raise LLMUnavailable("adapter %r needs an extra package: %s (see `pip install dd-llm[%s]`)" % (adapter, e, adapter)) from e
        self._local.usage = {"input_tokens": getattr(result, "input_tokens", 0), "output_tokens": getattr(result, "output_tokens", 0),
                             "cost_usd": getattr(result, "cost_usd", None)}
        if not result.success:
            errors = result.error_history or []
            raise RuntimeError(errors[-1]["error"] if errors else f"{adapter} call failed")
        return result.content


def make_llm(adapter: str = "mock", model: Optional[str] = None):
    """The LLM object for `--adapter` / `--model`."""
    if adapter == "mock":
        return MockLLM(model)
    return DDLLM(adapter, model, default_model(adapter))
