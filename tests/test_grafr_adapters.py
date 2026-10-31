"""LLM adapter plumbing. No real LLM is called here (a live check is a separate, manual step)."""
import sys
import types

import pytest

from graphlang.grafr.adapters import DDLLM, LLMUnavailable, MockLLM, make_llm, parse_node_llm, resolve_call


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


def test_parse_node_llm():
    assert parse_node_llm("ollama:gemma3:12b") == ("ollama", "gemma3:12b")
    assert parse_node_llm("claude_cli") == ("claude_cli", None) and parse_node_llm("claude_cli:") == ("claude_cli", None)
    assert parse_node_llm(":claude-haiku-5-5") == (None, "claude-haiku-5-5")        # a model on the run's adapter
    assert parse_node_llm(None) == (None, None) and parse_node_llm("") == (None, None)


def test_the_nodes_llm_beats_the_cli_which_beats_the_default():
    d = "claude-sonnet-5-5"
    assert resolve_call("claude_cli", "claude_cli:claude-haiku-5-5", "claude-opus-5-5", d) == ("claude_cli", "claude-haiku-5-5")   # node wins
    assert resolve_call("claude_cli", ":claude-haiku-5-5", "claude-opus-5-5", d) == ("claude_cli", "claude-haiku-5-5")
    assert resolve_call("claude_cli", None, "claude-opus-5-5", d) == ("claude_cli", "claude-opus-5-5")        # else --llm
    assert resolve_call("claude_cli", "claude_cli", "claude-opus-5-5", d) == ("claude_cli", "claude-opus-5-5")   # adapter only: the run's model
    assert resolve_call("claude_cli", None, None, d) == ("claude_cli", d)                                    # else the default


def test_a_node_can_name_another_adapter():
    # the run's --llm model belongs to the run's adapter, so it does not leak into the node's
    assert resolve_call("claude_cli", "ollama:gemma3", "claude-opus-5-5", "claude-sonnet-5-5") == ("ollama", "gemma3")
    assert resolve_call("claude_cli", "ollama", "claude-opus-5-5", "claude-sonnet-5-5") == ("ollama", None)      # that adapter's own default
    assert resolve_call("ollama", "claude_cli", None, None) == ("claude_cli", "claude-sonnet-5-5")              # claude_cli's default


def test_mock_answers_for_every_node():
    assert resolve_call("mock", "ollama:gemma3", None) == ("mock", "gemma3")
    assert resolve_call("mock", None, "x") == ("mock", "x")


def test_a_node_adapter_is_made_on_first_use(fake_dd_llm):
    llm = make_llm("claude_cli")
    assert llm.generate("a", model="m", adapter="ollama") == "reply to a" and fake_dd_llm["name"] == "ollama"
    assert llm.generate("b", model="m") == "reply to b"


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
