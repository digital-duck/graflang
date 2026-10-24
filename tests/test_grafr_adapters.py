"""LLM adapter plumbing. No real LLM is called here (a live check is a separate, manual step)."""
import asyncio
import sys
import types

import pytest

from graphlang.grafr import adapters
from graphlang.grafr.adapters import LLMUnavailable, MockLLM, SPLAdapterLLM, make_llm, resolve_model


def test_mock_is_the_default_and_needs_nothing():
    llm = make_llm()
    assert isinstance(llm, MockLLM) and llm.name == "mock"
    assert llm.generate("hello", model="m").startswith("[Mock LLM response from m for prompt: hello")
    assert make_llm("mock", "x").model_override == "x"


def test_resolve_model_rules(fake_spl):
    assert resolve_model("claude_cli", "ollama/gemma3", None) is None            # hint for another provider: ignored
    assert resolve_model("claude_cli", "ollama/gemma3", "claude-haiku-5-5") == "claude-haiku-5-5"   # --model wins
    assert resolve_model("claude_cli", "claude-sonnet-5-5", None) == "claude-sonnet-5-5"
    assert resolve_model("claude_cli", "gemma3", None) is None                   # not a Claude model
    assert resolve_model("ollama", "ollama/gemma3", None) == "gemma3"            # own prefix stripped
    assert resolve_model("openrouter", "qwen/qwen3", None) == "qwen/qwen3"       # openrouter models contain a slash
    assert resolve_model("mock", "anything/x", None) == "anything/x"
    assert resolve_model("claude_cli", None, None) is None


class _Result:
    def __init__(self, content):
        self.content = content


class _FakeAdapter:
    def __init__(self, **kw):
        self.kw, self.calls = kw, []

    async def generate(self, prompt, model="", max_tokens=4096, temperature=0.7, system=None):
        self.calls.append((prompt, model, max_tokens, temperature, system))
        await asyncio.sleep(0)
        return _Result(f"reply to {prompt}")


@pytest.fixture()
def fake_spl(monkeypatch):
    made = {}

    def get_adapter(name, **kw):
        if name == "nope":
            raise ValueError("Unknown adapter 'nope'. Available: claude_cli")
        made["adapter"] = _FakeAdapter(**kw)
        return made["adapter"]

    mod = types.ModuleType("spl3.adapters")
    mod.get_adapter = get_adapter
    mod._model_compatible = lambda name, model: model.startswith("claude-") if name == "claude_cli" else True
    monkeypatch.setitem(sys.modules, "spl3.adapters", mod)
    return made


def test_spl_adapter_wrapper_runs_the_async_adapter_synchronously(fake_spl):
    llm = make_llm("claude_cli", "claude-haiku-5-5")
    assert isinstance(llm, SPLAdapterLLM) and llm.name == "claude_cli"
    assert fake_spl["adapter"].kw == {"model": "claude-haiku-5-5"}
    assert llm.generate("ping", model="claude-haiku-5-5", temperature=0.1, junk=1) == "reply to ping"
    assert fake_spl["adapter"].calls == [("ping", "claude-haiku-5-5", 4096, 0.1, None)]    # junk option dropped


def test_it_also_works_when_an_event_loop_is_already_running(fake_spl):
    llm = make_llm("claude_cli")

    async def inside_a_loop():
        return llm.generate("again")

    assert asyncio.run(inside_a_loop()) == "reply to again"


def test_adapter_errors_become_llm_unavailable(fake_spl):
    with pytest.raises(LLMUnavailable, match="Unknown adapter"):
        make_llm("nope")


def test_missing_spl_py_gives_an_actionable_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "spl3", None)            # makes `import spl3...` raise ImportError
    monkeypatch.setitem(sys.modules, "spl3.adapters", None)
    with pytest.raises(LLMUnavailable, match="needs SPL.py"):
        make_llm("claude_cli")


def test_an_adapter_failure_propagates_from_a_run(fake_spl):
    class Boom(_FakeAdapter):
        async def generate(self, *a, **k):
            raise RuntimeError("Claude CLI timed out after 5s")

    sys.modules["spl3.adapters"].get_adapter = lambda name, **kw: Boom()
    with pytest.raises(RuntimeError, match="timed out"):
        make_llm("claude_cli").generate("x")
    assert adapters.LLMUnavailable.__mro__[1] is RuntimeError


def test_spl_py_path_env_var_finds_a_checkout(monkeypatch, tmp_path):
    import importlib.util
    if importlib.util.find_spec("spl3") is not None:
        pytest.skip("SPL.py is installed here, so the fallback path is not exercised")
    pkg = tmp_path / "spl3" / "adapters"
    pkg.mkdir(parents=True)
    (tmp_path / "spl3" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("def get_adapter(name, **kw):\n    return ('found', name)\n")
    for m in [k for k in sys.modules if k == "spl3" or k.startswith("spl3.")]:
        monkeypatch.delitem(sys.modules, m)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if "SPL.py" not in p])
    monkeypatch.setenv("SPL_PY_PATH", str(tmp_path))
    assert adapters._import_spl_get_adapter()("x") == ("found", "x")
    monkeypatch.undo()
