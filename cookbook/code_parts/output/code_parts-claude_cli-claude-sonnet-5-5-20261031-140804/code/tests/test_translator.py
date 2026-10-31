import subprocess
from unittest import mock

import pytest

from translator import core
from translator.config import (
    ADAPTERS, MAX_INPUT_CHARS, LLMSettings, default_model_for,
)


def test_prompt_contains_delimiters_and_languages():
    prompt = core.build_prompt("hello", "English", "French")
    assert "English" in prompt and "French" in prompt
    assert core.START_TAG in prompt and core.END_TAG in prompt
    assert "hello" in prompt


def test_prompt_auto_detect():
    assert "Detect" in core.build_system_prompt("Auto-detect", "French")


def test_api_key_prefers_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env")
    assert LLMSettings(adapter="openai", api_key="given").effective_api_key() == "given"
    assert LLMSettings(adapter="openai").effective_api_key() == "env"
    assert LLMSettings(adapter="claude_cli").effective_api_key() == ""


def test_repr_hides_key():
    assert "secret" not in repr(LLMSettings(api_key="secret"))


def test_default_model_for_other_adapter():
    assert default_model_for("openai") == ADAPTERS["openai"].models[0]


def test_validation_errors():
    s = LLMSettings(adapter="claude_cli", model="m")
    with pytest.raises(ValueError):
        core.translate("  ", "English", "French", s)
    with pytest.raises(ValueError):
        core.translate("x" * (MAX_INPUT_CHARS + 1), "English", "French", s)
    with pytest.raises(ValueError):
        core.translate("hi", "English", "English", s)
    with pytest.raises(ValueError):
        core.translate("hi", "English", "French", LLMSettings(adapter="nope", model="m"))
    with pytest.raises(ValueError):
        core.translate("hi", "English", "French", LLMSettings(adapter="claude_cli", model=" "))


def test_cli_success_uses_stdin():
    done = subprocess.CompletedProcess([], 0, stdout=" Bonjour \n", stderr="")
    with mock.patch("subprocess.run", return_value=done) as run:
        out = core.translate("-hello", "English", "French", LLMSettings(model="m"))
    assert out == "Bonjour"
    assert "-hello" in run.call_args.kwargs["input"]
    assert "-hello" not in run.call_args.args[0]


def test_cli_failure():
    done = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
    with mock.patch("subprocess.run", return_value=done):
        with pytest.raises(RuntimeError, match="boom"):
            core.translate("hi", "English", "French", LLMSettings(model="m"))


def test_cli_missing_binary():
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="not found"):
            core.translate("hi", "English", "French", LLMSettings(model="m"))


def test_cli_timeout_hides_text():
    err = subprocess.TimeoutExpired(cmd=["claude", "secret text"], timeout=1)
    with mock.patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError) as info:
            core.translate("secret text", "English", "French", LLMSettings(model="m"))
    assert "secret text" not in str(info.value)


def test_cli_empty_reply():
    done = subprocess.CompletedProcess([], 0, stdout="  ", stderr="")
    with mock.patch("subprocess.run", return_value=done):
        with pytest.raises(RuntimeError, match="empty"):
            core.translate("hi", "English", "French", LLMSettings(model="m"))
