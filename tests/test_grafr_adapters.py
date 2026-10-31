"""LLM adapter plumbing. No real LLM is called here (a live check is a separate, manual step)."""
import sys
import types

import pytest

from graphlang.grafr.adapters import DDLLM, LLMUnavailable, MockLLM, make_llm, resolve_model


def test_mock_is_the_default_and_needs_nothing():
    llm = make_llm()
    assert isinstance(llm, MockLLM) and llm.name == "mock"
    assert llm.generate("hello", model="m").startswith("[Mock LLM response from m for prompt: hello")
    assert make_llm("mock", "x").model_override == "x"


class _Response:
    def __init__(self, content="", success=True, error_history=None):
        self.content, self.success, self.error_history = content, success, error_history


class _FakeAdapter:
    def __init__(self, response=None):
        self.calls, self.response = [], response

    def call(self, prompt="", *, model="", **kw):
        self.calls.append((prompt, model, kw))
        return self.response or _Response(f"reply to {prompt}")


@pytest.fixture()
def fake_dd_llm(monkeypatch):
    """A stand-in `dd_llm` module, so these tests do not need the package (or a network)."""
    made = {}

    def get_adapter(name, **kw):
        if name == "nope":
            raise ValueError("Unknown adapter 'nope'. Available: claude_cli")
        made["adapter"] = _FakeAdapter()
        made["name"] = name
        return made["adapter"]

    mod = types.ModuleType("dd_llm")
    mod.get_adapter = get_adapter
    mod.model_compatible = lambda name, model: model.startswith("claude-") if name == "claude_cli" else True
    monkeypatch.setitem(sys.modules, "dd_llm", mod)
    return made


def test_resolve_model_rules(fake_dd_llm):
    assert resolve_model("claude_cli", "ollama/gemma3", None) is None            # hint for another provider: ignored
    assert resolve_model("claude_cli", "ollama/gemma3", "claude-haiku-5-5") == "claude-haiku-5-5"   # --model wins
    assert resolve_model("claude_cli", "claude-sonnet-5-5", None) == "claude-sonnet-5-5"
    assert resolve_model("claude_cli", "gemma3", None) is None                   # not a Claude model
    assert resolve_model("ollama", "ollama/gemma3", None) == "gemma3"            # own prefix stripped
    assert resolve_model("openrouter", "qwen/qwen3", None) == "qwen/qwen3"       # openrouter models contain a slash
    assert resolve_model("mock", "anything/x", None) == "anything/x"
    assert resolve_model("claude_cli", None, None) is None


def test_resolve_model_order_is_cli_then_node_then_default(fake_dd_llm):
    d = "claude-sonnet-5-5"
    assert resolve_model("claude_cli", "claude_cli/claude-haiku-5-5", "claude-opus-5-5", d) == "claude-haiku-5-5"   # the node's own wins
    assert resolve_model("claude_cli", None, "claude-opus-5-5", d) == "claude-opus-5-5"               # else the CLI's run-wide choice
    assert resolve_model("claude_cli", None, None, d) == d                                            # else the default
    assert resolve_model("claude_cli", "ollama/gemma3", "claude-opus-5-5", d) == "claude-opus-5-5"    # a hint for another adapter: CLI choice
    assert resolve_model("claude_cli", "ollama/gemma3", None, d) == d


def test_dd_llm_wrapper_calls_the_adapter(fake_dd_llm):
    llm = make_llm("claude_cli", "claude-haiku-5-5")
    assert isinstance(llm, DDLLM) and llm.name == "claude_cli" and llm.adapter_name == "claude_cli"
    assert llm.model_override == "claude-haiku-5-5"
    assert llm.generate("ping", model="claude-haiku-5-5", temperature=0.1, junk=1) == "reply to ping"
    assert fake_dd_llm["adapter"].calls == [("ping", "claude-haiku-5-5", {"temperature": 0.1})]     # junk option dropped


def test_adapter_errors_become_llm_unavailable(fake_dd_llm):
    with pytest.raises(LLMUnavailable, match="Unknown adapter"):
        make_llm("nope")


def test_missing_dd_llm_gives_an_actionable_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "dd_llm", None)            # makes `import dd_llm` raise ImportError
    with pytest.raises(LLMUnavailable, match="needs dd-llm"):
        make_llm("claude_cli")


def test_a_failed_call_raises_with_the_adapters_message(fake_dd_llm):
    llm = make_llm("claude_cli")
    fake_dd_llm["adapter"].response = _Response(success=False, error_history=[{"error": "Claude CLI timed out after 5s"}])
    with pytest.raises(RuntimeError, match="timed out"):
        llm.generate("x")
    assert LLMUnavailable.__mro__[1] is RuntimeError


def test_a_missing_provider_sdk_is_reported_as_unavailable(fake_dd_llm):
    llm = make_llm("openai")

    def boom(*a, **k):
        raise ImportError("No module named 'openai'")

    fake_dd_llm["adapter"].call = boom
    with pytest.raises(LLMUnavailable, match="needs an extra package"):
        llm.generate("x")


def test_with_the_real_dd_llm_echo_adapter():
    """End to end through the real package, no network: dd-llm's `echo` adapter returns the prompt."""
    pytest.importorskip("dd_llm")
    assert make_llm("echo").generate("ping") == "[Echo] ping"
