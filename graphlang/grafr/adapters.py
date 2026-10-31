"""LLM adapters for GENERATE nodes.

`make_llm(name, model)` returns an object with `.generate(prompt, model=None, **opts) -> str`.

* `mock`: no LLM; returns a canned string. The default, so nothing is billed unless you ask.
* anything else (`claude_cli`, `ollama`, `openrouter`, `anthropic`, `openai`, `gemini`, ...): the dd-llm
  adapter of that name (`dd_llm.get_adapter`). dd-llm is small and has no core dependencies, so GraphLang
  does not need SPL.py for plain LLM calls. `claude_cli` runs the Claude Code CLI with ANTHROPIC_API_KEY
  stripped, i.e. on your subscription, not the paid API.

(SPL.py is needed only for `procedure_ref` nodes; see procedures.py.)

DODA: the graph says *what* to generate; the provider and model are chosen when you run it
(`graf run --llm claude_cli:claude-haiku-5-5`). The model for a call is chosen in this order:
an explicit choice on the command line (`--model`, or the model in `--llm adapter:model`, or `llm:` in a bindings file) wins for every node;
else the node's own `model:` if it fits the adapter; else the adapter's default (claude_cli: claude-sonnet-5-5).
"""
from __future__ import annotations

import threading
from typing import Any, Optional


# Per-adapter default, used by a node that names no model of its own (or one for another adapter) when none is given on the
# command line. An adapter not listed (ollama, openrouter, ...) has none: the adapter's own default applies.
DEFAULT_MODELS = {"claude_cli": "claude-sonnet-5-5"}


def default_model(adapter: str) -> Optional[str]:
    return DEFAULT_MODELS.get(adapter)


class LLMUnavailable(RuntimeError):
    """The requested adapter cannot be created (dd-llm missing, unknown name, missing API key, ...)."""


def resolve_model(adapter: str, node_model: Optional[str], override: Optional[str], default: Optional[str] = None) -> Optional[str]:
    """Pick the model for one call: the explicit run-time choice, else the node's own model if it fits the adapter, else the default."""
    return override or _node_hint(adapter, node_model) or default


def _node_hint(adapter: str, node_model: Optional[str]) -> Optional[str]:
    """The node's `model:` as this adapter can use it, or None (a hint for another provider, or a model the adapter does not offer)."""
    if not node_model or adapter == "mock":
        return node_model or None
    if "/" in node_model and adapter != "openrouter":
        prefix, rest = node_model.split("/", 1)
        if prefix != adapter:
            return None                      # a hint for another provider, e.g. 'ollama/gemma3' under claude_cli
        node_model = rest
    try:
        from dd_llm import model_compatible
    except ImportError:
        return node_model
    return node_model if model_compatible(adapter, node_model) else None


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
        try:
            self._adapter = dd_llm.get_adapter(name)
        except ValueError as e:                      # unknown adapter, or a required key / setting is missing
            raise LLMUnavailable(str(e)) from e
        self.name = name
        self.adapter_name = name
        self.model_override = model                  # chosen on the command line: beats every node's own model
        self.default_model = default                 # used when a node names no usable model
        self._local = threading.local()

    def last_usage(self) -> Optional[dict]:
        """Tokens and cost the adapter reported for this thread's latest call, if it did."""
        return getattr(self._local, "usage", None)

    def generate(self, prompt: str, model: Optional[str] = None, **opts: Any) -> str:
        kwargs = {k: v for k, v in opts.items() if k in ("max_tokens", "temperature", "system") and v is not None}
        try:
            result = self._adapter.call(prompt, model=model or "", **kwargs)
        except ImportError as e:                     # the provider's SDK is an optional extra of dd-llm
            raise LLMUnavailable("adapter %r needs an extra package: %s (see `pip install dd-llm[%s]`)" % (self.name, e, self.name)) from e
        self._local.usage = {"input_tokens": getattr(result, "input_tokens", 0), "output_tokens": getattr(result, "output_tokens", 0),
                             "cost_usd": getattr(result, "cost_usd", None)}
        if not result.success:
            errors = result.error_history or []
            raise RuntimeError(errors[-1]["error"] if errors else f"{self.name} call failed")
        return result.content


def make_llm(adapter: str = "mock", model: Optional[str] = None):
    """The LLM object for `--adapter` / `--model`."""
    if adapter == "mock":
        return MockLLM(model)
    return DDLLM(adapter, model, default_model(adapter))
